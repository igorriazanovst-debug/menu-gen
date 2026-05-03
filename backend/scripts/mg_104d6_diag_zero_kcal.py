"""
MG-104d-6 diag: разбор рецептов с kcal=0.

Идём по всем Recipe.kcal==0 (после d-5 их 7), для каждого:
  - выводим title, servings, servings_normalized, dish_weight_g_calc
  - перебираем ingredients_norm и для каждой строки помечаем, что мешает посчитать ккал:
      * skip:true               — отмечен как «пропустить» в d-2
      * composite:true          — составной ингредиент
      * no_qty / bad_qty / zero_qty
      * kbju_missing            — нет name_canon в ingredient_kbju.json
      * unit_unknown            — неизвестная единица
      * ok                      — масса посчитана и КБЖУ найдены
  - считаем суммарную грамматуру и kcal_total для контроля
  - на агрегаты по причинам собираем сводку по справочникам:
      * uniq name_canon без записи в kbju (с count)
      * uniq (name_canon, unit_canon) для штучных без specific
      * uniq unit_canon неизвестных

Выход:
  /tmp/menugen/mg104d6_zero_kcal_per_row.tsv      — построчный разбор
  /tmp/menugen/mg104d6_zero_kcal_summary.tsv      — агрегат по причинам
  /tmp/menugen/mg104d6_zero_kcal_kbju_missing.tsv — name_canon без КБЖУ + примеры
  /tmp/menugen/mg104d6_zero_kcal_units.tsv        — неизвестные единицы

Запуск:
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d6_diag_zero_kcal.py'

Параметры (env):
  MG104D6_KCAL_THRESHOLD=0  — обрабатывать рецепты с kcal <= threshold (по умолчанию 0)
  MG104D6_DATA_DIR=/app/data
  MG104D6_OUT_DIR=/tmp/menugen
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal

from django.apps import apps

# ---------- конфиг ----------
DATA_DIR = os.environ.get("MG104D6_DATA_DIR", "/app/data")
OUT_DIR = os.environ.get("MG104D6_OUT_DIR", "/tmp/menugen")
KBJU_PATH = os.path.join(DATA_DIR, "ingredient_kbju.json")
PIECES_G_PATH = os.path.join(DATA_DIR, "pieces_g.tsv")
PIECES_DEFAULT_PATH = os.path.join(DATA_DIR, "pieces_default_g.tsv")
DENSITY_PATH = os.path.join(DATA_DIR, "density.tsv")

KCAL_THRESHOLD = Decimal(os.environ.get("MG104D6_KCAL_THRESHOLD", "0"))

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- единицы (повторяем формат d-4) ----------
VOLUME_ML = {
    "мл": 1.0, "л": 1000.0,
    "ст.л.": 15.0, "ч.л.": 5.0,
    "ст": 240.0, "капля": 0.05,
}
PIECE_UNITS = {
    "шт", "зубчик", "головка", "кочан", "пучок", "ломтик", "долька",
    "банка", "бутылка", "пакет", "пачка", "плитка", "кубик",
    "лист", "стручок", "веточка", "гроздь",
}
WEIGHT_G = {"г": 1.0, "кг": 1000.0}
PINCH_G = {"щепотка": 0.4}


# ---------- загрузка справочников (как в d-4) ----------
def load_kbju(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cleaned = {}
    for name, rec in data.items():
        if not isinstance(rec, dict):
            continue
        cal = rec.get("calories")
        if cal is None:
            continue
        try:
            key = (name or "").strip().lower().replace("ё", "е")
            cleaned[key] = {
                "kcal":     float(cal),
                "proteins": float(rec.get("proteins") or 0),
                "fats":     float(rec.get("fats") or 0),
                "carbs":    float(rec.get("carbs") or 0),
            }
        except (TypeError, ValueError):
            continue
    return cleaned


def load_tsv(path, key_cols, val_col):
    out = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                if len(key_cols) == 1:
                    key = (row[key_cols[0]] or "").strip()
                else:
                    key = tuple((row[c] or "").strip() for c in key_cols)
                val = float(row[val_col])
            except (KeyError, ValueError, TypeError):
                continue
            if key and val is not None:
                out[key] = val
    return out


def to_grams(name, unit, qty, pieces_g, pieces_default, density):
    """Возвращает (grams, reason). reason из набора:
       weight/volume/pinch/piece_specific/piece_default/piece_fallback/empty_as_g/
       no_qty/bad_qty/zero_qty/unknown_unit:<u>"""
    if qty is None:
        return None, "no_qty"
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return None, "bad_qty"
    if qty <= 0:
        return None, "zero_qty"

    u = (unit or "").strip()
    n = (name or "").strip()

    if u in WEIGHT_G:
        return qty * WEIGHT_G[u], "weight"
    if u in VOLUME_ML:
        d = density.get(n, 1.0)
        return qty * VOLUME_ML[u] * d, "volume"
    if u in PINCH_G:
        return qty * PINCH_G[u], "pinch"
    if u in PIECE_UNITS:
        g = pieces_g.get((n, u))
        if g is not None:
            return qty * g, "piece_specific"
        g = pieces_default.get(u)
        if g is not None:
            return qty * g, "piece_default"
        return qty * 50.0, "piece_fallback"
    if u == "":
        return qty, "empty_as_g"
    return None, f"unknown_unit:{u}"


# ---------- main ----------
print("[mg-104d-6 diag] загрузка справочников")
for p in (KBJU_PATH, PIECES_G_PATH, PIECES_DEFAULT_PATH, DENSITY_PATH):
    if not os.path.exists(p):
        print(f"[FATAL] нет файла: {p}", file=sys.stderr)
        sys.exit(1)

kbju = load_kbju(KBJU_PATH)
pieces_g = load_tsv(PIECES_G_PATH, ("name_canon", "unit_canon"), "grams_per_unit")
pieces_default = load_tsv(PIECES_DEFAULT_PATH, ("unit_canon",), "grams_per_unit")
density = load_tsv(DENSITY_PATH, ("name_canon",), "density")

print(f"[mg-104d-6 diag] kbju={len(kbju)} pieces={len(pieces_g)} "
      f"pieces_default={len(pieces_default)} density={len(density)}")

Recipe = apps.get_model("recipes", "Recipe")

qs = (Recipe.objects
      .filter(kcal__lte=KCAL_THRESHOLD)
      .order_by("id")
      .only("id", "title", "servings", "kcal", "proteins", "fats", "carbs", "povar_raw"))

# поле servings_normalized — добавлено в d-5
try:
    _ = Recipe._meta.get_field("servings_normalized")
    HAS_SN = True
except Exception:
    HAS_SN = False

if HAS_SN:
    qs = qs.only("id", "title", "servings", "servings_normalized",
                 "kcal", "proteins", "fats", "carbs", "povar_raw")

total = qs.count()
print(f"[mg-104d-6 diag] recipes with kcal<={KCAL_THRESHOLD}: {total}")

per_row_path = os.path.join(OUT_DIR, "mg104d6_zero_kcal_per_row.tsv")
summary_path = os.path.join(OUT_DIR, "mg104d6_zero_kcal_summary.tsv")
miss_kbju_path = os.path.join(OUT_DIR, "mg104d6_zero_kcal_kbju_missing.tsv")
miss_units_path = os.path.join(OUT_DIR, "mg104d6_zero_kcal_units.tsv")

reason_counter = Counter()
miss_kbju = defaultdict(lambda: {"count": 0, "examples": []})  # name_canon -> {count, examples=[(name_orig,unit,qty)]}
miss_units = Counter()
miss_pieces_specific = Counter()  # (name_canon, unit) — нет в pieces_g
recipe_summary = []  # (id, title, sn, kcal_total_calc, grams_total, n_skip, n_kbju_missing, n_unit_unknown, n_no_qty, n_used)

with open(per_row_path, "w", encoding="utf-8", newline="") as f_row:
    w_row = csv.writer(f_row, delimiter="\t")
    w_row.writerow([
        "recipe_id", "title",
        "row_idx", "name_orig", "name_canon", "unit_canon", "quantity",
        "skip", "composite", "matched",
        "grams_calc", "grams_reason",
        "kbju_found", "kcal_row",
        "row_status",
    ])

    for r in qs.iterator(chunk_size=200):
        povar = r.povar_raw or {}
        ings = povar.get("ingredients_norm") or []
        sn = getattr(r, "servings_normalized", None) if HAS_SN else None
        sn_eff = int(sn or r.servings or 1)

        kcal_total_calc = 0.0
        grams_total = 0.0

        n_total = 0
        n_skip = 0
        n_composite = 0
        n_no_qty = 0
        n_unit_unknown = 0
        n_kbju_missing = 0
        n_used = 0

        for idx, row in enumerate(ings):
            if not isinstance(row, dict):
                continue
            n_total += 1

            name_orig = row.get("name_orig") or ""
            name_canon = row.get("name_canon") or ""
            unit_canon = row.get("unit_canon") or ""
            qty = row.get("quantity")
            skip = bool(row.get("skip"))
            composite = bool(row.get("composite"))
            matched = bool(row.get("matched"))

            row_status = ""
            grams_calc = None
            grams_reason = ""
            kb_found = False
            kcal_row = 0.0

            if skip:
                n_skip += 1
                row_status = "skip"
            elif composite:
                n_composite += 1
                row_status = "composite"
            else:
                grams_calc, grams_reason = to_grams(
                    name_canon, unit_canon, qty,
                    pieces_g, pieces_default, density,
                )
                if grams_calc is None:
                    if grams_reason in ("no_qty", "zero_qty", "bad_qty"):
                        n_no_qty += 1
                        row_status = grams_reason
                    elif grams_reason.startswith("unknown_unit"):
                        n_unit_unknown += 1
                        row_status = grams_reason
                        miss_units[unit_canon] += 1
                    else:
                        row_status = grams_reason
                else:
                    grams_total += grams_calc
                    if grams_reason == "piece_default":
                        miss_pieces_specific[(name_canon, unit_canon)] += 1

                    name_key = name_canon.strip().lower().replace("ё", "е")
                    kb = kbju.get(name_key)
                    if kb is None:
                        n_kbju_missing += 1
                        row_status = "kbju_missing"
                        rec = miss_kbju[name_key]
                        rec["count"] += 1
                        if len(rec["examples"]) < 5:
                            rec["examples"].append(
                                f"{name_orig}|{unit_canon}|{qty}"
                            )
                    else:
                        kb_found = True
                        n_used += 1
                        factor = grams_calc / 100.0
                        kcal_row = kb["kcal"] * factor
                        kcal_total_calc += kcal_row
                        row_status = "ok"

            reason_counter[row_status] += 1

            w_row.writerow([
                r.id, (r.title or "")[:80],
                idx, name_orig[:60], name_canon[:60],
                unit_canon, qty,
                int(skip), int(composite), int(matched),
                round(grams_calc, 1) if grams_calc is not None else "",
                grams_reason,
                int(kb_found), round(kcal_row, 2),
                row_status,
            ])

        recipe_summary.append((
            r.id, (r.title or "")[:80],
            int(r.servings or 0), int(sn or 0),
            float(r.kcal or 0),
            round(kcal_total_calc / max(sn_eff, 1), 1),
            round(grams_total, 1),
            n_total, n_skip, n_composite, n_no_qty, n_unit_unknown, n_kbju_missing, n_used,
        ))

# ---------- сводка ----------
with open(summary_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow([
        "recipe_id", "title",
        "servings_old", "servings_normalized",
        "kcal_db",
        "kcal_per_serving_calc",
        "grams_total",
        "rows_total", "rows_skip", "rows_composite",
        "rows_no_qty", "rows_unit_unknown", "rows_kbju_missing", "rows_used",
    ])
    for row in recipe_summary:
        w.writerow(row)

# kbju_missing — отсортировано по частоте
miss_kbju_sorted = sorted(miss_kbju.items(), key=lambda kv: -kv[1]["count"])
with open(miss_kbju_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["name_canon", "count", "examples_name_orig|unit|qty"])
    for name, rec in miss_kbju_sorted:
        w.writerow([name, rec["count"], " || ".join(rec["examples"])])

with open(miss_units_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["unit_canon", "count"])
    for u, c in miss_units.most_common():
        w.writerow([u, c])

# ---------- stdout ----------
print("\n========== ИТОГ ==========")
print(f"recipes processed: {total}")
print(f"\nраспределение row_status:")
for k, c in reason_counter.most_common():
    print(f"  {k:20s}  {c}")

print(f"\nуникальных name_canon без КБЖУ: {len(miss_kbju)}")
print("TOP-15 name_canon без КБЖУ (по частоте):")
for name, rec in miss_kbju_sorted[:15]:
    print(f"  {rec['count']:3d}  {name!r}")

print(f"\nуникальных unknown unit_canon: {len(miss_units)}")
for u, c in miss_units.most_common(10):
    print(f"  {c:3d}  {u!r}")

print(f"\nштучные без specific (name,unit) -> piece_default: {len(miss_pieces_specific)}")
for (n, u), c in miss_pieces_specific.most_common(10):
    print(f"  {c:3d}  {n!r}  {u!r}")

print(f"\nфайлы:")
print(f"  per_row:        {per_row_path}")
print(f"  recipe_summary: {summary_path}")
print(f"  kbju_missing:   {miss_kbju_path}")
print(f"  units_unknown:  {miss_units_path}")

print("\n========== РЕЦЕПТЫ С kcal<=0 ==========")
print(f"{'id':>5}  {'s':>2}  {'sn':>2}  {'kcal_db':>7}  {'kcal_calc':>9}  {'grams':>6}  "
      f"{'tot':>3}  {'skip':>4}  {'noqty':>5}  {'unitU':>5}  {'kbjuM':>5}  {'used':>4}  title")
for row in recipe_summary:
    rid, title, s, sn, kcal_db, kcal_calc, grams, ntot, nskip, ncomp, nnoq, nunkU, nkbM, nused = row
    print(f"{rid:>5}  {s:>2}  {sn:>2}  {kcal_db:>7.1f}  {kcal_calc:>9.1f}  "
          f"{grams:>6.0f}  {ntot:>3}  {nskip:>4}  {nnoq:>5}  {nunkU:>5}  {nkbM:>5}  {nused:>4}  "
          f"{title}")
