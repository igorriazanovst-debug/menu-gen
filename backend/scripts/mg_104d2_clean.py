"""
MG-104d-3c clean (rewrite): применяет synonyms.yaml к Recipe.povar_raw.
Создаёт/обновляет povar_raw.ingredients_norm на основе ingredients_site.

Логика:
  1. Загрузить synonyms.yaml: units, manual_synonyms, auto_synonyms, composite, skip
  2. Построить обратные индексы:
     - alias_to_canon: всякая строка из manual+auto -> canon
     - canon_set: множество всех canon (если canon встречается как имя — оставляем как canon)
  3. Для каждого Recipe с непустым povar_raw:
     - для каждого ingredients_site[*]:
       * чистим name (нижний регистр, обрезка хвостов "по вкусу", "для подачи" и т.п.)
       * unit -> unit_canon (по units из yaml; "по вкусу" -> skip)
       * name_canon = lookup(alias_to_canon, normalized_name)
                       fallback: само normalized_name (matched=False)
       * skip = name_clean in SKIP
       * composite = name_clean in COMPOSITE
  4. Пишем обратно povar_raw.ingredients_norm; bulk_update.

Запуск:
  docker compose exec backend python manage.py shell -c \
    "exec(open('/app/scripts/mg_104d2_clean.py').read())"
"""
import csv
import json
import os
import re
from collections import Counter

import yaml
from django.apps import apps
from django.db import transaction


YAML_PATH = "/app/scripts/data/synonyms.yaml"
OUT_DIR = "/tmp/menugen"
BATCH = 500

os.makedirs(OUT_DIR, exist_ok=True)

with open(YAML_PATH, encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

UNITS_MAP: dict = cfg.get("units") or {}
MANUAL: dict = cfg.get("manual_synonyms") or {}
AUTO: dict = cfg.get("auto_synonyms") or {}
COMPOSITE: set = set(cfg.get("composite") or [])
SKIP: set = set(cfg.get("skip") or [])

# ─── чистка хвостов ───────────────────────────────────────────────────────────

GARBAGE_TAILS = [
    r"для подачи",
    r"для украшения",
    r"для сервировки",
    r"для смазывания",
    r"для жарки",
    r"для обжаривания",
    r"для соуса",
    r"для теста",
    r"для начинки",
    r"для крема",
    r"для маринада",
    r"для глазури",
    r"для гарнира",
    r"для посыпки",
    r"крупного помола",
    r"мелкого помола",
    r"среднего помола",
    r"по вкусу",
    r"свежемолотый",
    r"по желанию",
    r"опционально",
]
TAIL_RE = re.compile(r"\s*(,\s*)?(" + "|".join(GARBAGE_TAILS) + r")\s*$", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
PUNCT_TAIL_RE = re.compile(r"[,;:.\-\s]+$")


def clean_name(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip().replace("ё", "е")
    # хвосты
    for _ in range(3):
        new = TAIL_RE.sub("", s).strip()
        if new == s:
            break
        s = new
    s = PUNCT_TAIL_RE.sub("", s)
    s = WS_RE.sub(" ", s).strip()
    return s


def norm_unit(u: str) -> str:
    if not u:
        return ""
    u_low = u.lower().strip().replace("ё", "е")
    if u_low in UNITS_MAP:
        return UNITS_MAP[u_low]
    return u_low


# ─── обратный индекс alias -> canon ───────────────────────────────────────────

alias_to_canon: dict = {}
canon_set: set = set()

for canon, aliases in MANUAL.items():
    canon_n = clean_name(canon)
    canon_set.add(canon_n)
    alias_to_canon[canon_n] = canon_n
    for a in (aliases or []):
        an = clean_name(a)
        if an and an not in alias_to_canon:
            alias_to_canon[an] = canon_n

for canon, aliases in AUTO.items():
    canon_n = clean_name(canon)
    canon_set.add(canon_n)
    if canon_n not in alias_to_canon:
        alias_to_canon[canon_n] = canon_n
    for a in (aliases or []):
        an = clean_name(a)
        if an and an not in alias_to_canon:
            alias_to_canon[an] = canon_n

print(f"[yaml] {len(MANUAL)} manual canons, {len(AUTO)} auto canons, "
      f"{len(alias_to_canon)} aliases total, {len(SKIP)} skip, {len(COMPOSITE)} composite")


# ─── ядро ─────────────────────────────────────────────────────────────────────

def normalize_one(item: dict) -> dict:
    name_orig = (item.get("name") or item.get("name_orig") or "").strip()
    unit_orig = (item.get("unit") or item.get("unit_orig") or "").strip()
    qty_raw = item.get("quantity") or item.get("amount") or item.get("qty")

    try:
        quantity = float(qty_raw) if qty_raw not in (None, "") else None
    except (TypeError, ValueError):
        quantity = None

    name_clean = clean_name(name_orig)
    unit_canon = norm_unit(unit_orig)
    if unit_orig and unit_orig.lower().strip() == "по вкусу":
        unit_canon = "по_вкусу"

    skip = (name_clean in SKIP) or (unit_canon == "по_вкусу")
    composite = name_clean in COMPOSITE

    if name_clean in alias_to_canon:
        name_canon = alias_to_canon[name_clean]
        matched = True
    elif name_clean in canon_set:
        name_canon = name_clean
        matched = True
    else:
        name_canon = name_clean
        matched = False

    return {
        "name_canon": name_canon,
        "name_orig": name_orig,
        "unit_canon": unit_canon,
        "unit_orig": unit_orig,
        "quantity": quantity,
        "skip": skip,
        "composite": composite,
        "matched": matched,
    }


Recipe = apps.get_model("recipes", "Recipe")

unmatched_counter: Counter = Counter()
unmatched_examples: dict = {}
stats = Counter()

qs = Recipe.objects.exclude(povar_raw__isnull=True).only("id", "povar_raw").iterator(chunk_size=BATCH)
buf = []
n_recipes = 0

with transaction.atomic():
    for r in qs:
        n_recipes += 1
        raw = r.povar_raw or {}
        ing_site = raw.get("ingredients_site") or []
        norm_list = []
        for it in ing_site:
            n = normalize_one(it)
            norm_list.append(n)
            stats["items"] += 1
            if n["skip"]:
                stats["skip"] += 1
            elif n["composite"]:
                stats["composite"] += 1
            elif n["matched"]:
                stats["matched"] += 1
            else:
                stats["unmatched"] += 1
                unmatched_counter[n["name_canon"]] += 1
                if n["name_canon"] not in unmatched_examples:
                    unmatched_examples[n["name_canon"]] = n["name_orig"]

        raw["ingredients_norm"] = norm_list
        r.povar_raw = raw
        buf.append(r)

        if len(buf) >= BATCH:
            Recipe.objects.bulk_update(buf, ["povar_raw"])
            buf.clear()

    if buf:
        Recipe.objects.bulk_update(buf, ["povar_raw"])
        buf.clear()

# ─── отчёты ───────────────────────────────────────────────────────────────────

unmatched_path = os.path.join(OUT_DIR, "mg104d2_unmatched.tsv")
with open(unmatched_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    w.writerow(["name_canon", "n_total", "name_orig_example"])
    for name, n in unmatched_counter.most_common():
        w.writerow([name, n, unmatched_examples.get(name, "")])

print(json.dumps({
    "recipes_processed": n_recipes,
    "items_total": stats["items"],
    "matched": stats["matched"],
    "skip": stats["skip"],
    "composite": stats["composite"],
    "unmatched": stats["unmatched"],
    "unique_unmatched": len(unmatched_counter),
    "unmatched_file": unmatched_path,
}, ensure_ascii=False, indent=2))
