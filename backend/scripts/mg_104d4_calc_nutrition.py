"""
MG-104d-4: расчёт КБЖУ по povar_raw.ingredients_norm и запись в
Recipe.kcal/proteins/fats/carbs (на 1 порцию).

Источники:
  - ingredient_kbju.json   — справочник КБЖУ на 100 г (формат {name_canon: {...}})
  - pieces_g.tsv           — конверсия штук в граммы (по name_canon + unit_canon)
  - pieces_default_g.tsv   — fallback по unit_canon
  - density.tsv            — плотность для объёмных единиц (мл/л/ст.л./ч.л./ст/капля)

Запуск:
  python manage.py shell < /app/scripts/mg_104d4_calc_nutrition.py
  # или для холостого прогона (без записи в БД):
  MG104D4_DRY_RUN=1 python manage.py shell < /app/scripts/mg_104d4_calc_nutrition.py
  # ограничение по числу рецептов (для отладки):
  MG104D4_LIMIT=50 python manage.py shell < /app/scripts/mg_104d4_calc_nutrition.py

Выход:
  - запись в Recipe.kcal/proteins/fats/carbs (на 1 порцию, округление до 0.1)
  - отчёт покрытия в /tmp/menugen/mg104d4_calc_report.tsv
  - сводка в stdout
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.db import transaction

# ---------- конфигурация ----------
DATA_DIR = os.environ.get("MG104D4_DATA_DIR", "/tmp/menugen")
KBJU_PATH = os.environ.get("MG104D4_KBJU_PATH", os.path.join(DATA_DIR, "ingredient_kbju.json"))
PIECES_G_PATH = os.path.join(DATA_DIR, "pieces_g.tsv")
PIECES_DEFAULT_PATH = os.path.join(DATA_DIR, "pieces_default_g.tsv")
DENSITY_PATH = os.path.join(DATA_DIR, "density.tsv")
REPORT_PATH = os.path.join(DATA_DIR, "mg104d4_calc_report.tsv")

DRY_RUN = os.environ.get("MG104D4_DRY_RUN", "").lower() in ("1", "true", "yes")
LIMIT = int(os.environ.get("MG104D4_LIMIT", "0") or 0)

VOLUME_ML = {
    "мл": 1.0,
    "л": 1000.0,
    "ст.л.": 15.0,
    "ч.л.": 5.0,
    "ст": 240.0,    # cup
    "капля": 0.05,  # «капля» — особый кейс, плотность всё равно учитываем
}
PIECE_UNITS = {"шт", "зубчик", "головка", "кочан", "пучок", "ломтик", "долька",
               "банка", "бутылка", "пакет", "пачка", "плитка", "кубик",
               "лист", "стручок", "веточка", "гроздь"}
WEIGHT_G = {"г": 1.0, "кг": 1000.0}
PINCH_G = {"щепотка": 0.4}
PIECE_FALLBACK_DEFAULT_G = 50.0  # самый последний fallback, если нет в default

# ---------- загрузка справочников ----------
def load_kbju(path):
    """Читает ingredient_kbju.json (формат d-3c: ключи calories/proteins/fats/carbs).
    Нормализует имена (lower, ё→е, strip) — как в d-3c.
    Записи с calories is None пропускает (надёжно посчитать нельзя)."""
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

def load_tsv(path, key_cols, val_col, val_cast=float):
    """key_cols=tuple, возвращает dict с ключом-кортежем (или строкой если 1 колонка)."""
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
                # последняя запись по ключу побеждает (на случай дубликатов)
                out[key] = val
    return out

# ---------- конверсия в граммы ----------
class GramsResolver:
    def __init__(self, pieces_g, pieces_default, density):
        self.pieces_g = pieces_g                # {(name, unit): grams}
        self.pieces_default = pieces_default    # {unit: grams}
        self.density = density                  # {name: g/ml}, default 1.0
        self.miss_units = Counter()
        self.miss_pieces = Counter()

    def density_for(self, name):
        return self.density.get(name or "", 1.0)

    def to_grams(self, name, unit, qty):
        """Возвращает (grams, reason) или (None, reason)."""
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

        # 1. вес
        if u in WEIGHT_G:
            return qty * WEIGHT_G[u], "weight"

        # 2. объём (с плотностью)
        if u in VOLUME_ML:
            return qty * VOLUME_ML[u] * self.density_for(n), "volume"

        # 3. щепотка
        if u in PINCH_G:
            return qty * PINCH_G[u], "pinch"

        # 4. штучные единицы
        if u in PIECE_UNITS:
            g = self.pieces_g.get((n, u))
            if g is not None:
                return qty * g, "piece_specific"
            g = self.pieces_default.get(u)
            if g is not None:
                self.miss_pieces[(n, u)] += 1
                return qty * g, "piece_default"
            self.miss_pieces[(n, u)] += 1
            return qty * PIECE_FALLBACK_DEFAULT_G, "piece_fallback"

        # 5. пустой unit_canon → трактуем как граммы (последний резерв)
        if u == "":
            return qty, "empty_as_g"

        # 6. неизвестная единица
        self.miss_units[u] += 1
        return None, f"unknown_unit:{u}"

# ---------- основной цикл ----------
def calc_recipe_kbju(ingredients_norm, kbju, resolver):
    """Возвращает dict с накопленными КБЖУ + статистика по строкам."""
    acc = {"kcal": 0.0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0}
    stats = {
        "rows_total": 0,
        "rows_skipped": 0,
        "rows_composite": 0,
        "rows_no_qty": 0,
        "rows_unit_unknown": 0,
        "rows_kbju_missing": 0,
        "rows_used": 0,
        "grams_total": 0.0,
        "grams_with_kbju": 0.0,
    }
    if not isinstance(ingredients_norm, list):
        return acc, stats

    for row in ingredients_norm:
        if not isinstance(row, dict):
            continue
        stats["rows_total"] += 1
        if row.get("skip"):
            stats["rows_skipped"] += 1
            continue
        if row.get("composite"):
            stats["rows_composite"] += 1
            continue

        name = row.get("name_canon") or ""
        unit = row.get("unit_canon") or ""
        qty = row.get("quantity")

        # нормализация name под формат kbju (lower + ё→е)
        name_key = name.strip().lower().replace("ё", "е")

        grams, reason = resolver.to_grams(name, unit, qty)
        if grams is None:
            if reason in ("no_qty", "zero_qty", "bad_qty"):
                stats["rows_no_qty"] += 1
            else:
                stats["rows_unit_unknown"] += 1
            continue

        stats["grams_total"] += grams
        kb = kbju.get(name_key)
        if kb is None:
            stats["rows_kbju_missing"] += 1
            continue

        stats["rows_used"] += 1
        stats["grams_with_kbju"] += grams
        factor = grams / 100.0
        acc["kcal"]     += kb["kcal"] * factor
        acc["proteins"] += kb["proteins"] * factor
        acc["fats"]     += kb["fats"] * factor
        acc["carbs"]    += kb["carbs"] * factor

    return acc, stats

def round_dec(x):
    return Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

def main():
    print(f"[mg-104d-4] DRY_RUN={DRY_RUN} LIMIT={LIMIT or 'none'}")
    print(f"[mg-104d-4] kbju: {KBJU_PATH}")
    print(f"[mg-104d-4] pieces_g: {PIECES_G_PATH}")
    print(f"[mg-104d-4] pieces_default: {PIECES_DEFAULT_PATH}")
    print(f"[mg-104d-4] density: {DENSITY_PATH}")

    for p in (KBJU_PATH, PIECES_G_PATH, PIECES_DEFAULT_PATH, DENSITY_PATH):
        if not os.path.exists(p):
            print(f"[FATAL] нет файла: {p}", file=sys.stderr)
            sys.exit(1)

    kbju = load_kbju(KBJU_PATH)
    pieces_g = load_tsv(PIECES_G_PATH, ("name_canon", "unit_canon"), "grams_per_unit")
    pieces_default = load_tsv(PIECES_DEFAULT_PATH, ("unit_canon",), "grams_per_unit")
    density = load_tsv(DENSITY_PATH, ("name_canon",), "density")
    print(f"[mg-104d-4] loaded: kbju={len(kbju)} pieces={len(pieces_g)} "
          f"pieces_default={len(pieces_default)} density={len(density)}")

    resolver = GramsResolver(pieces_g, pieces_default, density)
    Recipe = apps.get_model("recipes", "Recipe")

    qs = (Recipe.objects
          .exclude(povar_raw__isnull=True)
          .order_by("id")
          .only("id", "title", "servings", "povar_raw"))
    if LIMIT:
        qs = qs[:LIMIT]

    total = qs.count() if not LIMIT else min(LIMIT, qs.count())
    print(f"[mg-104d-4] recipes to process: {total}")

    written = 0
    skipped_no_norm = 0
    skipped_zero_kcal = 0
    coverage_buckets = Counter()  # 0%, 1-25, 26-50, 51-75, 76-99, 100%
    rows_for_report = []

    chunk = []
    CHUNK_SIZE = 500

    def flush_chunk(rs):
        if not rs or DRY_RUN:
            return
        Recipe.objects.bulk_update(
            rs, ["kcal", "proteins", "fats", "carbs"], batch_size=500
        )

    for idx, r in enumerate(qs.iterator(chunk_size=500), 1):
        povar = r.povar_raw or {}
        ing = povar.get("ingredients_norm")
        if not ing:
            skipped_no_norm += 1
            rows_for_report.append((r.id, r.title, 0, 0, 0, 0, 0, 0, 0, 0, 0, "no_ingredients_norm"))
            continue

        acc, stats = calc_recipe_kbju(ing, kbju, resolver)
        servings = max(int(r.servings or 1), 1)

        kcal_per = acc["kcal"] / servings
        prot_per = acc["proteins"] / servings
        fat_per = acc["fats"] / servings
        carb_per = acc["carbs"] / servings

        # покрытие по граммам — сколько % массы рецепта смогли посчитать
        coverage = 0.0
        if stats["grams_total"] > 0:
            coverage = stats["grams_with_kbju"] / stats["grams_total"] * 100.0
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

        if kcal_per <= 0:
            skipped_zero_kcal += 1

        r.kcal = round_dec(kcal_per)
        r.proteins = round_dec(prot_per)
        r.fats = round_dec(fat_per)
        r.carbs = round_dec(carb_per)
        chunk.append(r)
        written += 1

        rows_for_report.append((
            r.id, r.title[:80], servings,
            stats["rows_total"], stats["rows_used"],
            stats["rows_kbju_missing"], stats["rows_unit_unknown"],
            round(stats["grams_total"], 1), round(stats["grams_with_kbju"], 1),
            round(coverage, 1),
            float(r.kcal),
            "ok",
        ))

        if len(chunk) >= CHUNK_SIZE:
            with transaction.atomic():
                flush_chunk(chunk)
            chunk.clear()
            if idx % 1000 == 0:
                print(f"[mg-104d-4] processed {idx}/{total}")

    if chunk:
        with transaction.atomic():
            flush_chunk(chunk)
        chunk.clear()

    # ---------- отчёт ----------
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "recipe_id", "title", "servings",
            "rows_total", "rows_used",
            "rows_kbju_missing", "rows_unit_unknown",
            "grams_total", "grams_with_kbju", "coverage_pct",
            "kcal_per_serving", "status",
        ])
        for row in rows_for_report:
            w.writerow(row)
    print(f"[mg-104d-4] report → {REPORT_PATH}")

    # ---------- сводка ----------
    print("\n========== ИТОГ ==========")
    print(f"recipes processed: {total}")
    print(f"  written (kcal/p/f/c set): {written}")
    print(f"  skipped (no ingredients_norm): {skipped_no_norm}")
    print(f"  zero kcal (анализировать): {skipped_zero_kcal}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("\nПокрытие по массе ингредиентов (% рецептов):")
    for k in ("0%", "1-25%", "25-50%", "50-75%", "75-99%", "100%"):
        v = coverage_buckets.get(k, 0)
        pct = v / max(written, 1) * 100
        print(f"  {k:>8}: {v:5d}  ({pct:5.1f}%)")

    if resolver.miss_pieces:
        print("\nTop-20 (name, unit) без specific шт→г (использован fallback):")
        for (nm, u), c in resolver.miss_pieces.most_common(20):
            print(f"  {c:5d}  {nm!r:30}  {u!r}")
    if resolver.miss_units:
        print("\nTop-20 неизвестных unit_canon:")
        for u, c in resolver.miss_units.most_common(20):
            print(f"  {c:5d}  {u!r}")

main()
