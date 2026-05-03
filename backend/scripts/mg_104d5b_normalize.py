"""
MG-104d-5b: Корректный пересчёт dish_weight_g_calc, servings_normalized
и (по возможности) kcal/p/f/c для всех рецептов через полную модель
расчёта граммов из MG-104d-4.

Зачем:
  В оригинальном MG-104d-5 функция estimate_grams() обрабатывала только
  единицы [г, кг, мл, л, шт]. Объёмные (ст, ст.л., ч.л., капля), штучные
  (зубчик, головка, пучок, ломтик, банка, бутылка, пакет, пачка, плитка,
  кубик, лист, стручок, веточка, гроздь) и щепотка считались через
  pieces_default[unit] = 0.0 (потому что таких ключей в pieces_default_g.tsv
  нет). Из-за этого dish_weight_g_calc для рецептов с такими ингредиентами
  систематически занижался → servings_normalized тоже занижался →
  kcal/порция пересчитывался криво.

Что делает d-5b:
  1) Считает dw_new и kcal_total/p/f/c через полный to_grams (как в d-4/d-7b)
     — единый источник правды.
  2) Определяет servings_normalized по той же логике d-5 (is_unit_serving
     + normalize_servings), но уже на корректном dw_new.
  3) Записывает kcal/p/f/c из расчёта (kcal_total / sn_new) ТОЛЬКО если
     coverage по массе >= MIN_COVERAGE_PCT. Иначе старый kcal оставляем.
  4) dw_calc и servings_normalized записываются всегда — они не зависят
     от справочника KBJU, только от справочников весов (которые почти 100%).
  5) Старые значения сохраняем под суффиксом _pre5b в povar_raw.
  6) Идемпотентен: повторный запуск даст те же результаты, потому что
     kcal не "rescale * scale", а считается из ингредиентов с нуля.

Запуск:
  # dry-run
  python manage.py shell < /app/scripts/mg_104d5b_normalize.py
  # apply
  MG104D5B_APPLY=1 python manage.py shell < /app/scripts/mg_104d5b_normalize.py

Параметры (env):
  MG104D5B_APPLY=1                — реальная запись
  MG104D5B_LIMIT=N                — обработать только N рецептов (0 = все)
  MG104D5B_DATA_DIR=/app/data     — справочники
  MG104D5B_MIN_COVERAGE=50.0      — порог записи нового kcal (%)
  MG104D5B_SERVING_G=300          — целевая порция (г)
"""
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.db import transaction

# ---------- конфигурация ----------
APPLY = os.environ.get("MG104D5B_APPLY", "").lower() in ("1", "true", "yes")
LIMIT = int(os.environ.get("MG104D5B_LIMIT", "0") or 0)
DATA_DIR = os.environ.get("MG104D5B_DATA_DIR", "/app/data")
MIN_COVERAGE_PCT = float(os.environ.get("MG104D5B_MIN_COVERAGE", "50.0"))
SERVING_G = float(os.environ.get("MG104D5B_SERVING_G", "300"))

KBJU_PATH = os.path.join(DATA_DIR, "ingredient_kbju.json")
KBJU_ALIASES_PATH = os.path.join(DATA_DIR, "ingredient_kbju_aliases.tsv")
PIECES_G_PATH = os.path.join(DATA_DIR, "pieces_g.tsv")
PIECES_DEFAULT_PATH = os.path.join(DATA_DIR, "pieces_default_g.tsv")
DENSITY_PATH = os.path.join(DATA_DIR, "density.tsv")

REPORT_DIR = "/tmp/menugen"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = os.path.join(REPORT_DIR, f"mg104d5b_report_{TS}.tsv")
SUMMARY_PATH = os.path.join(REPORT_DIR, f"mg104d5b_summary_{TS}.txt")
LOW_COV_PATH = os.path.join(REPORT_DIR, f"mg104d5b_low_coverage_{TS}.tsv")

VOLUME_ML = {
    "мл": 1.0, "л": 1000.0, "ст.л.": 15.0, "ч.л.": 5.0, "ст": 240.0, "капля": 0.05,
}
PIECE_UNITS = {"шт", "зубчик", "головка", "кочан", "пучок", "ломтик", "долька",
               "банка", "бутылка", "пакет", "пачка", "плитка", "кубик",
               "лист", "стручок", "веточка", "гроздь"}
WEIGHT_G = {"г": 1.0, "кг": 1000.0}
PINCH_G = {"щепотка": 0.4}
PIECE_FALLBACK_DEFAULT_G = 50.0

# is_unit_serving regex'ы — копия из d-5
UNIT_TITLE_RE = re.compile(
    r"\b("
    r"печенье|печений|печенюшк|"
    r"торт|тортик|"
    r"пирог|пирожк|пирожн|"
    r"булочк|булк|"
    r"маффин|капкейк|кекс|"
    r"безе|меренг|"
    r"пахлав|"
    r"тарталет|корзиноч|"
    r"трюфел|конфет|карамел|"
    r"зефир|пастил|мармелад|"
    r"пряник|"
    r"вафл|"
    r"круассан|эклер|профитрол|"
    r"макарон|"
    r"чизкейк|чиз-кейк|"
    r"роллет|рулет|"
    r"бискви|"
    r"кейк-?поп|"
    r"шарик|сердечк|плитк|плиточк|"
    r"мороженое|щербет|сорбет|"
    r"мусс|желе|"
    r"сгущ|"
    r"глазур"
    r")",
    re.IGNORECASE,
)
UNIT_EXCLUDE_RE = re.compile(
    r"\b("
    r"холодец|заливн|"
    r"желе\s+из\s+(мяс|курин|говяж|свин|рыб|телятин|индейк|утк|баран|язык|петух)|"
    r"мясн(ое|ой)\s+желе|"
    r"рыбн(ое|ой)\s+желе"
    r")",
    re.IGNORECASE,
)


# ---------- загрузка справочников ----------
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
    # MG-104d-5c: алиасы (доп. ключи, ссылающиеся на существующие записи)
    aliases_path = globals().get('KBJU_ALIASES_PATH')
    if aliases_path and os.path.exists(aliases_path):
        added = 0
        skipped_no_canonical = []
        skipped_already = []
        with open(aliases_path, encoding='utf-8') as af:
            reader = csv.DictReader(af, delimiter='\t')
            for row in reader:
                alias = (row.get('alias') or '').strip().lower().replace('ё','е')
                canon = (row.get('canonical') or '').strip().lower().replace('ё','е')
                if not alias or not canon:
                    continue
                if alias in cleaned:
                    skipped_already.append(alias)
                    continue
                if canon not in cleaned:
                    skipped_no_canonical.append((alias, canon))
                    continue
                cleaned[alias] = cleaned[canon]
                added += 1
        print(f'[mg-104d-5c] aliases applied: +{added} '
              f'(already_in_kbju={len(skipped_already)}, '
              f'canonical_missing={len(skipped_no_canonical)})')
        if skipped_no_canonical:
            for a, c in skipped_no_canonical[:10]:
                print(f'  WARN: alias {a!r} -> canonical {c!r} not in KBJU')
    return cleaned


def load_tsv(path, key_cols, val_col, val_cast=float):
    out = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                if len(key_cols) == 1:
                    key = (row[key_cols[0]] or "").strip()
                else:
                    key = tuple((row[c] or "").strip() for c in key_cols)
                val = val_cast(row[val_col])
            except (KeyError, ValueError, TypeError):
                continue
            if key and val is not None:
                out[key] = val
    return out


class GramsResolver:
    def __init__(self, pieces_g, pieces_default, density):
        self.pieces_g = pieces_g
        self.pieces_default = pieces_default
        self.density = density

    def density_for(self, name):
        return self.density.get(name or "", 1.0)

    def to_grams(self, name, unit, qty):
        if qty is None:
            return None
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            return None
        if qty <= 0:
            return None
        u = (unit or "").strip()
        n = (name or "").strip()
        if u in WEIGHT_G:
            return qty * WEIGHT_G[u]
        if u in VOLUME_ML:
            return qty * VOLUME_ML[u] * self.density_for(n)
        if u in PINCH_G:
            return qty * PINCH_G[u]
        if u in PIECE_UNITS:
            g = self.pieces_g.get((n, u))
            if g is not None:
                return qty * g
            g = self.pieces_default.get(u)
            if g is not None:
                return qty * g
            return qty * PIECE_FALLBACK_DEFAULT_G
        if u == "":
            return qty
        return None


def calc_recipe_kbju(ingredients_norm, kbju, resolver):
    """Возвращает суммарные KBJU (на ВЕСЬ рецепт) и stats.
    grams_total — суммарная масса всех ингредиентов с распознанными граммами.
    """
    acc = {"kcal": 0.0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0}
    stats = {"rows_total": 0, "rows_used": 0, "grams_total": 0.0, "grams_with_kbju": 0.0}
    if not isinstance(ingredients_norm, list):
        return acc, stats
    for row in ingredients_norm:
        if not isinstance(row, dict):
            continue
        stats["rows_total"] += 1
        if row.get("skip") or row.get("composite"):
            continue
        name = row.get("name_canon") or ""
        unit = row.get("unit_canon") or ""
        qty = row.get("quantity")
        name_key = name.strip().lower().replace("ё", "е")
        grams = resolver.to_grams(name, unit, qty)
        if grams is None:
            continue
        stats["grams_total"] += grams
        kb = kbju.get(name_key)
        if kb is None:
            continue
        stats["rows_used"] += 1
        stats["grams_with_kbju"] += grams
        factor = grams / 100.0
        acc["kcal"]     += kb["kcal"] * factor
        acc["proteins"] += kb["proteins"] * factor
        acc["fats"]     += kb["fats"] * factor
        acc["carbs"]    += kb["carbs"] * factor
    return acc, stats


def is_unit_serving(title, servings, dw_calc, kcal_old):
    """Копия из d-5: определяет «штучный» рецепт."""
    t = (title or "").lower()
    if UNIT_EXCLUDE_RE.search(t):
        return False, ""
    if UNIT_TITLE_RE.search(t):
        return True, "title_match"
    if servings >= 12 and 0 < dw_calc < 1500:
        return True, "many_small_servings"
    if kcal_old and servings > 0 and dw_calc > 0:
        density = (float(kcal_old) * int(servings)) / dw_calc
        if density > 6.0 and servings >= 8:
            return True, "high_kcal_density"
    if servings >= 16 and 0 < dw_calc < 3000 and kcal_old is not None and kcal_old < 100:
        return True, "low_kcal_many_servings"
    return False, ""


def normalize_servings(dw):
    """Единый принцип: sn = max(1, round(dw / SERVING_G))."""
    return max(1, round(dw / SERVING_G)), "by_weight"


def round_dec(x):
    return Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def main():
    print(f"[mg-104d-5b] APPLY={APPLY} LIMIT={LIMIT or 'all'}")
    print(f"[mg-104d-5b] DATA_DIR={DATA_DIR} MIN_COVERAGE_PCT={MIN_COVERAGE_PCT}")
    print(f"[mg-104d-5b] SERVING_G={SERVING_G}")

    for p in (KBJU_PATH, PIECES_G_PATH, PIECES_DEFAULT_PATH, DENSITY_PATH):
        if not os.path.exists(p):
            print(f"[FATAL] нет файла: {p}", file=sys.stderr)
            sys.exit(1)

    kbju = load_kbju(KBJU_PATH)
    pieces_g = load_tsv(PIECES_G_PATH, ("name_canon", "unit_canon"), "grams_per_unit")
    pieces_default = load_tsv(PIECES_DEFAULT_PATH, ("unit_canon",), "grams_per_unit")
    density = load_tsv(DENSITY_PATH, ("name_canon",), "density")
    print(f"[mg-104d-5b] loaded: kbju={len(kbju)} pieces={len(pieces_g)} "
          f"pieces_default={len(pieces_default)} density={len(density)}")

    resolver = GramsResolver(pieces_g, pieces_default, density)
    Recipe = apps.get_model("recipes", "Recipe")

    qs = (Recipe.objects
          .exclude(povar_raw__isnull=True)
          .exclude(povar_raw={})
          .order_by("id")
          .only("id", "title", "servings", "servings_normalized",
                "povar_raw", "kcal", "proteins", "fats", "carbs"))
    if LIMIT:
        qs = qs[:LIMIT]

    total = qs.count()
    print(f"[mg-104d-5b] recipes to process: {total}")

    os.makedirs(REPORT_DIR, exist_ok=True)
    rows = []
    counters = Counter()
    methods = Counter()
    coverage_buckets = Counter()
    to_save = []

    chunk = []
    CHUNK_SIZE = 500

    def flush_chunk(rs):
        if not rs or not APPLY:
            return
        Recipe.objects.bulk_update(
            rs, ["kcal", "proteins", "fats", "carbs",
                 "servings_normalized", "povar_raw"],
            batch_size=500,
        )

    for idx, r in enumerate(qs.iterator(chunk_size=500), 1):
        povar = r.povar_raw or {}
        ing = povar.get("ingredients_norm")

        # текущие значения
        servings_old = int(r.servings or 1)
        sn_old = r.servings_normalized
        kcal_old = float(r.kcal) if r.kcal is not None else None
        dw_old = povar.get("dish_weight_g_calc")
        try:
            dw_old_f = float(dw_old) if dw_old is not None else None
        except (TypeError, ValueError):
            dw_old_f = None

        # без ingredients_norm — пропускаем (нечего считать)
        if not ing:
            counters["skipped_no_norm"] += 1
            rows.append({
                "id": r.id, "title": (r.title or "")[:80],
                "servings_old": servings_old,
                "sn_old": sn_old if sn_old is not None else "",
                "sn_new": "", "method": "skip:no_norm",
                "dw_old": dw_old_f if dw_old_f is not None else "",
                "dw_new": "", "coverage_pct": "",
                "kcal_old": round(kcal_old, 1) if kcal_old is not None else "",
                "kcal_new": "", "kcal_written": "no",
                "density_old": "", "density_new": "",
                "is_unit": "", "rows_used": 0, "rows_total": 0,
                "action": "no_change",
            })
            continue

        acc, stats = calc_recipe_kbju(ing, kbju, resolver)
        dw_new = stats["grams_total"]
        coverage = (stats["grams_with_kbju"] / stats["grams_total"] * 100.0
                    if stats["grams_total"] > 0 else 0.0)

        # покрытие — корзины
        if coverage == 0:
            coverage_buckets["0%"] += 1
        elif coverage < 25:
            coverage_buckets["1-25%"] += 1
        elif coverage < 50:
            coverage_buckets["25-50%"] += 1
        elif coverage < 75:
            coverage_buckets["50-75%"] += 1
        elif coverage < 100:
            coverage_buckets["75-99%"] += 1
        else:
            coverage_buckets["100%"] += 1

        # LOW COVERAGE → полный skip (БД не трогаем).
        # Причина: при coverage < MIN_COVERAGE_PCT мы плохо считаем массу
        # ингредиентов рецепта, поэтому ни dw_new, ни kcal_new, ни sn_new,
        # выведенный из dw_new, не являются достоверными.
        if coverage < MIN_COVERAGE_PCT:
            counters["skipped_low_coverage"] += 1
            density_old_v = ""
            if kcal_old is not None and dw_old_f and dw_old_f > 0 and sn_old:
                density_old_v = round(float(kcal_old) * sn_old / dw_old_f, 2)
            rows.append({
                "id": r.id, "title": (r.title or "")[:80],
                "servings_old": servings_old,
                "sn_old": sn_old if sn_old is not None else "",
                "sn_new": "", "method": "skip:low_coverage",
                "dw_old": round(dw_old_f, 1) if dw_old_f is not None else "",
                "dw_new": round(dw_new, 1),
                "coverage_pct": round(coverage, 1),
                "kcal_old": round(kcal_old, 1) if kcal_old is not None else "",
                "kcal_new": "", "kcal_written": "no",
                "density_old": density_old_v, "density_new": "",
                "is_unit": "", "rows_used": stats["rows_used"],
                "rows_total": stats["rows_total"],
                "action": "skip:low_coverage",
            })
            continue

        # determine sn_new
        is_unit, unit_reason = is_unit_serving(r.title or "", servings_old, dw_new, kcal_old)
        if is_unit:
            sn_new = servings_old
            method = f"unit_kept:{unit_reason}"
        else:
            sn_new, method = normalize_servings(dw_new)

        methods[method] += 1

        # kcal на 1 порцию по новому расчёту
        if sn_new <= 0:
            sn_new = 1
        kcal_new_per = acc["kcal"] / sn_new
        prot_new_per = acc["proteins"] / sn_new
        fat_new_per = acc["fats"] / sn_new
        carb_new_per = acc["carbs"] / sn_new

        counters["kcal_written"] += 1

        # плотности (для отчёта)
        density_old_v = ""
        if kcal_old is not None and dw_old_f and dw_old_f > 0 and sn_old:
            density_old_v = round(float(kcal_old) * sn_old / dw_old_f, 2)
        density_new_v = ""
        if dw_new > 0:
            density_new_v = round(float(kcal_new_per) * sn_new / dw_new, 2)

        # формирование изменений в БД
        changed_fields = []
        if dw_old_f != round(dw_new, 2):
            changed_fields.append("dw")
        if sn_old != sn_new:
            changed_fields.append("sn")
        changed_fields.append("kcal")

        if changed_fields:
            counters["any_change"] += 1
            counters[f"changed:{','.join(changed_fields)}"] += 1

            # обновляем povar_raw (старые значения в _pre5b)
            new_pr = dict(povar)
            if "dish_weight_g_calc_pre5b" not in new_pr:
                new_pr["dish_weight_g_calc_pre5b"] = dw_old_f
            if "servings_normalized_pre5b" not in new_pr:
                new_pr["servings_normalized_pre5b"] = sn_old
            if "kcal_pre5b" not in new_pr:
                new_pr["kcal_pre5b"] = kcal_old
            new_pr["dish_weight_g_calc"] = round(dw_new, 2)
            new_pr["mg_104d5b_v"] = 1
            r.povar_raw = new_pr
            r.servings_normalized = sn_new
            r.kcal = round_dec(kcal_new_per)
            r.proteins = round_dec(prot_new_per)
            r.fats = round_dec(fat_new_per)
            r.carbs = round_dec(carb_new_per)
            chunk.append(r)
        else:
            counters["no_change"] += 1

        rows.append({
            "id": r.id, "title": (r.title or "")[:80],
            "servings_old": servings_old,
            "sn_old": sn_old if sn_old is not None else "",
            "sn_new": sn_new, "method": method,
            "dw_old": round(dw_old_f, 1) if dw_old_f is not None else "",
            "dw_new": round(dw_new, 1),
            "coverage_pct": round(coverage, 1),
            "kcal_old": round(kcal_old, 1) if kcal_old is not None else "",
            "kcal_new": round(kcal_new_per, 1),
            "kcal_written": "yes",
            "density_old": density_old_v,
            "density_new": density_new_v,
            "is_unit": "yes" if is_unit else "no",
            "rows_used": stats["rows_used"],
            "rows_total": stats["rows_total"],
            "action": ",".join(changed_fields) if changed_fields else "no_change",
        })

        if len(chunk) >= CHUNK_SIZE:
            with transaction.atomic():
                flush_chunk(chunk)
            chunk.clear()
            if idx % 1000 == 0:
                print(f"[mg-104d-5b] processed {idx}/{total}")

    if chunk:
        with transaction.atomic():
            flush_chunk(chunk)
        chunk.clear()

    # ---------- отчёт TSV ----------
    fieldnames = list(rows[0].keys()) if rows else []
    with open(REPORT_PATH, "w", encoding="utf-8", newline="") as f:
        if fieldnames:
            w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            w.writeheader()
            w.writerows(rows)

    # ---------- отдельный отчёт low-coverage ----------
    low_cov_rows = [x for x in rows if x["action"] == "skip:low_coverage"]
    if low_cov_rows:
        with open(LOW_COV_PATH, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            w.writeheader()
            w.writerows(sorted(low_cov_rows, key=lambda x: float(x["coverage_pct"]) if x["coverage_pct"] != "" else 0))

    # ---------- сводка ----------
    lines = [
        "MG-104d-5b summary",
        f"timestamp: {TS}",
        f"APPLY={APPLY} LIMIT={LIMIT or 'all'}",
        f"MIN_COVERAGE_PCT={MIN_COVERAGE_PCT} SERVING_G={SERVING_G}",
        "",
        f"total processed:                {total}",
        f"  skipped (no ingredients_norm):{counters['skipped_no_norm']:>5}",
        f"  skipped (low coverage):       {counters['skipped_low_coverage']:>5}  → {LOW_COV_PATH}",
        f"  any change:                   {counters['any_change']:>5}",
        f"  no change:                    {counters['no_change']:>5}",
        f"  kcal переписан:               {counters['kcal_written']:>5}",
        "",
        "Покрытие по массе ингредиентов:",
    ]
    for k in ("0%", "1-25%", "25-50%", "50-75%", "75-99%", "100%"):
        v = coverage_buckets.get(k, 0)
        lines.append(f"  {k:>8}: {v:5d}")
    lines.append("")
    lines.append("Методы определения sn_new:")
    for m, v in methods.most_common():
        lines.append(f"  {m:<28}: {v}")
    lines.append("")
    lines.append("Типы изменений (поля):")
    for k, v in counters.items():
        if k.startswith("changed:"):
            lines.append(f"  {k:<40}: {v}")
    lines.append("")

    # топ по разнице sn (для контроля)
    rows_changed = [x for x in rows if x["action"] != "no_change" and x["action"] != ""]
    top_sn = sorted(
        [x for x in rows_changed if isinstance(x["sn_new"], int) and isinstance(x["sn_old"], int)],
        key=lambda x: abs(int(x["sn_new"]) - int(x["sn_old"])), reverse=True
    )[:30]
    lines.append("TOP-30 по разнице sn (sn_old → sn_new):")
    lines.append(f"  {'id':>6}  {'so':>3}  {'sno':>3}  {'snn':>3}  {'method':<24}  "
                 f"{'dw_old':>7}  {'dw_new':>7}  {'cov%':>5}  title")
    for x in top_sn:
        lines.append(
            f"  {x['id']:>6}  {x['servings_old']:>3}  {str(x['sn_old']):>3}  "
            f"{x['sn_new']:>3}  {x['method']:<24}  "
            f"{str(x['dw_old']):>7}  {str(x['dw_new']):>7}  "
            f"{str(x['coverage_pct']):>5}  {x['title']}"
        )
    lines.append("")

    # топ по разнице dw
    top_dw = sorted(
        [x for x in rows_changed if x["dw_old"] not in ("", None) and isinstance(x["dw_new"], (int, float))],
        key=lambda x: abs(float(x["dw_new"]) - float(x["dw_old"])), reverse=True
    )[:30]
    lines.append("TOP-30 по абсолютной разнице dw_calc:")
    lines.append(f"  {'id':>6}  {'dw_old':>8}  {'dw_new':>8}  {'so':>3}  {'sno':>3}  "
                 f"{'snn':>3}  title")
    for x in top_dw:
        lines.append(
            f"  {x['id']:>6}  {str(x['dw_old']):>8}  {str(x['dw_new']):>8}  "
            f"{x['servings_old']:>3}  {str(x['sn_old']):>3}  {x['sn_new']:>3}  {x['title']}"
        )

    summary = "\n".join(lines)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(summary)

    print()
    print(summary)
    print()
    print(f"[mg-104d-5b] report:  {REPORT_PATH}")
    print(f"[mg-104d-5b] summary: {SUMMARY_PATH}")
    print(f"[mg-104d-5b] APPLY={APPLY} — {'записано в БД' if APPLY else 'DRY-RUN, БД не тронута'}")


main()
