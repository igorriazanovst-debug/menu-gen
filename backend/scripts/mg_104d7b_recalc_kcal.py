"""
MG-104d-7b (v2): пересчёт kcal+dw_calc для рецептов с физически невозможной
плотностью (density > DENSITY_LIMIT ккал/г) при правдоподобном dw_calc
(dw_calc >= DW_MIN_G г).

Ключевая идея: битым может быть и kcal, и dw_calc одновременно. Поэтому
из ингредиентов считаем И калорийность, И вес блюда (grams_total), и
сохраняем оба значения. Старый dw_calc уезжает в povar_raw['dish_weight_g_calc_pre7b']
для трассировки.

Запись производится только если:
  - coverage по массе >= MIN_COVERAGE_PCT (мусорные расчёты не пишем);
  - новая плотность (kcal_new * sn / dw_new) <= DENSITY_LIMIT.

Идемпотентен: повторный запуск отбирает только тех, кто всё ещё битый по
актуальным kcal/dw_calc.

Запуск:
  # dry-run
  python manage.py shell < /app/scripts/mg_104d7b_recalc_kcal.py
  # apply
  MG104D7B_APPLY=1 python manage.py shell < /app/scripts/mg_104d7b_recalc_kcal.py

Параметры (env):
  MG104D7B_APPLY=1                  — реальная запись
  MG104D7B_DENSITY_LIMIT=9.0        — порог плотности (ккал/г)
  MG104D7B_DW_MIN_G=100.0           — минимальный dw_calc для кандидата
  MG104D7B_MIN_COVERAGE=50.0        — порог покрытия по массе (%)
  MG104D7B_DATA_DIR=/app/data       — где лежат справочники
"""
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.db import transaction

# ---------- конфигурация ----------
APPLY = os.environ.get("MG104D7B_APPLY", "").lower() in ("1", "true", "yes")
DENSITY_LIMIT = float(os.environ.get("MG104D7B_DENSITY_LIMIT", "9.0"))
DW_MIN_G = float(os.environ.get("MG104D7B_DW_MIN_G", "100.0"))
MIN_COVERAGE_PCT = float(os.environ.get("MG104D7B_MIN_COVERAGE", "50.0"))

DATA_DIR = os.environ.get("MG104D7B_DATA_DIR", "/app/data")
KBJU_PATH = os.path.join(DATA_DIR, "ingredient_kbju.json")
PIECES_G_PATH = os.path.join(DATA_DIR, "pieces_g.tsv")
PIECES_DEFAULT_PATH = os.path.join(DATA_DIR, "pieces_default_g.tsv")
DENSITY_PATH = os.path.join(DATA_DIR, "density.tsv")

REPORT_DIR = "/tmp/menugen"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_OK = os.path.join(REPORT_DIR, f"mg104d7b_fixed_{TS}.tsv")
REPORT_FAIL = os.path.join(REPORT_DIR, f"mg104d7b_unfixed_{TS}.tsv")

VOLUME_ML = {
    "мл": 1.0, "л": 1000.0, "ст.л.": 15.0, "ч.л.": 5.0, "ст": 240.0, "капля": 0.05,
}
PIECE_UNITS = {"шт", "зубчик", "головка", "кочан", "пучок", "ломтик", "долька",
               "банка", "бутылка", "пакет", "пачка", "плитка", "кубик",
               "лист", "стручок", "веточка", "гроздь"}
WEIGHT_G = {"г": 1.0, "кг": 1000.0}
PINCH_G = {"щепотка": 0.4}
PIECE_FALLBACK_DEFAULT_G = 50.0


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
            return qty * VOLUME_ML[u] * self.density_for(n), "volume"
        if u in PINCH_G:
            return qty * PINCH_G[u], "pinch"
        if u in PIECE_UNITS:
            g = self.pieces_g.get((n, u))
            if g is not None:
                return qty * g, "piece_specific"
            g = self.pieces_default.get(u)
            if g is not None:
                return qty * g, "piece_default"
            return qty * PIECE_FALLBACK_DEFAULT_G, "piece_fallback"
        if u == "":
            return qty, "empty_as_g"
        return None, f"unknown_unit:{u}"


def calc_recipe_kbju(ingredients_norm, kbju, resolver):
    """Возвращает суммарные KBJU по всему рецепту (всем порциям) и stats.
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
        grams, _ = resolver.to_grams(name, unit, qty)
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


def round_dec(x):
    return Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def main():
    print(f"[mg-104d-7b] APPLY={APPLY}")
    print(f"[mg-104d-7b] DENSITY_LIMIT={DENSITY_LIMIT} DW_MIN_G={DW_MIN_G} MIN_COVERAGE_PCT={MIN_COVERAGE_PCT}")
    print(f"[mg-104d-7b] DATA_DIR={DATA_DIR}")

    for p in (KBJU_PATH, PIECES_G_PATH, PIECES_DEFAULT_PATH, DENSITY_PATH):
        if not os.path.exists(p):
            print(f"[FATAL] нет файла: {p}", file=sys.stderr)
            sys.exit(1)

    kbju = load_kbju(KBJU_PATH)
    pieces_g = load_tsv(PIECES_G_PATH, ("name_canon", "unit_canon"), "grams_per_unit")
    pieces_default = load_tsv(PIECES_DEFAULT_PATH, ("unit_canon",), "grams_per_unit")
    density = load_tsv(DENSITY_PATH, ("name_canon",), "density")
    print(f"[mg-104d-7b] loaded: kbju={len(kbju)} pieces={len(pieces_g)} "
          f"pieces_default={len(pieces_default)} density={len(density)}")

    resolver = GramsResolver(pieces_g, pieces_default, density)
    Recipe = apps.get_model("recipes", "Recipe")

    # --- отбор кандидатов ---
    candidates = []
    for r in Recipe.objects.filter(kcal__gt=0).only(
            "id", "title", "servings", "servings_normalized", "povar_raw",
            "kcal", "proteins", "fats", "carbs"):
        sn = r.servings_normalized or r.servings or 1
        pr = r.povar_raw or {}
        dw = pr.get("dish_weight_g_calc") or 0
        try:
            dw = float(dw)
        except (TypeError, ValueError):
            continue
        if dw < DW_MIN_G:
            continue
        density_old = float(r.kcal) * sn / dw if dw > 0 else 0
        if density_old > DENSITY_LIMIT:
            candidates.append((r, sn, dw, density_old))

    print(f"[mg-104d-7b] кандидатов: {len(candidates)}")
    if not candidates:
        print("[mg-104d-7b] нечего делать — выход.")
        return

    os.makedirs(REPORT_DIR, exist_ok=True)
    fixed_rows = []
    unfixed_rows = []
    reasons = Counter()
    to_save = []

    for r, sn, dw_old, density_old in candidates:
        povar = r.povar_raw or {}
        ing = povar.get("ingredients_norm")
        if not ing:
            reasons["no_ingredients_norm"] += 1
            unfixed_rows.append((
                r.id, r.title[:80], sn, round(dw_old, 1), round(density_old, 2),
                "", "", "", "", "", "no_ingredients_norm",
            ))
            continue

        acc, stats = calc_recipe_kbju(ing, kbju, resolver)
        coverage = 0.0
        if stats["grams_total"] > 0:
            coverage = stats["grams_with_kbju"] / stats["grams_total"] * 100.0

        kcal_per = acc["kcal"] / sn
        prot_per = acc["proteins"] / sn
        fat_per = acc["fats"] / sn
        carb_per = acc["carbs"] / sn
        dw_new = stats["grams_total"]
        density_new = (kcal_per * sn / dw_new) if dw_new > 0 else 0.0

        if coverage < MIN_COVERAGE_PCT:
            reasons[f"low_coverage(<{MIN_COVERAGE_PCT:.0f}%)"] += 1
            unfixed_rows.append((
                r.id, r.title[:80], sn, round(dw_old, 1), round(density_old, 2),
                round(coverage, 1), round(kcal_per, 1),
                round(dw_new, 1), round(density_new, 2),
                stats["rows_used"], "low_coverage",
            ))
            continue

        if dw_new <= 0:
            reasons["dw_new_zero"] += 1
            unfixed_rows.append((
                r.id, r.title[:80], sn, round(dw_old, 1), round(density_old, 2),
                round(coverage, 1), round(kcal_per, 1),
                round(dw_new, 1), round(density_new, 2),
                stats["rows_used"], "dw_new_zero",
            ))
            continue

        if density_new > DENSITY_LIMIT:
            reasons["still_dense_after_recalc"] += 1
            unfixed_rows.append((
                r.id, r.title[:80], sn, round(dw_old, 1), round(density_old, 2),
                round(coverage, 1), round(kcal_per, 1),
                round(dw_new, 1), round(density_new, 2),
                stats["rows_used"], "still_dense",
            ))
            continue

        # рецепт лечится — обновляем kcal/p/f/c и dw_calc в povar_raw
        kcal_old = float(r.kcal)
        r.kcal = round_dec(kcal_per)
        r.proteins = round_dec(prot_per)
        r.fats = round_dec(fat_per)
        r.carbs = round_dec(carb_per)

        new_pr = dict(povar)
        # сохраняем старый dw на случай отката/сравнения (только если ещё не сохранён)
        if "dish_weight_g_calc_pre7b" not in new_pr:
            new_pr["dish_weight_g_calc_pre7b"] = dw_old
        new_pr["dish_weight_g_calc"] = round(dw_new, 2)
        new_pr["dish_weight_g_calc_v7b"] = True
        r.povar_raw = new_pr

        to_save.append(r)
        fixed_rows.append((
            r.id, r.title[:80], sn,
            round(dw_old, 1), round(dw_new, 1),
            round(density_old, 2), round(density_new, 2),
            round(coverage, 1),
            round(kcal_old, 1), float(r.kcal),
            stats["rows_used"], stats["rows_total"],
        ))

    with open(REPORT_OK, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "recipe_id", "title", "servings_norm",
            "dw_old", "dw_new",
            "density_old", "density_new",
            "coverage_pct",
            "kcal_old", "kcal_new",
            "rows_used", "rows_total",
        ])
        for row in fixed_rows:
            w.writerow(row)
    with open(REPORT_FAIL, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "recipe_id", "title", "servings_norm",
            "dw_old", "density_old",
            "coverage_pct", "kcal_new_calc",
            "dw_new_calc", "density_new_calc",
            "rows_used", "reason",
        ])
        for row in unfixed_rows:
            w.writerow(row)

    print(f"[mg-104d-7b] кандидатов: {len(candidates)}")
    print(f"[mg-104d-7b] чинится: {len(fixed_rows)}")
    print(f"[mg-104d-7b] не чинится: {len(unfixed_rows)}")
    if reasons:
        print("[mg-104d-7b] причины 'не чинится':")
        for k, v in reasons.most_common():
            print(f"   {k}: {v}")
    print(f"[mg-104d-7b] отчёт OK    → {REPORT_OK}")
    print(f"[mg-104d-7b] отчёт FAIL  → {REPORT_FAIL}")

    if not APPLY:
        print("[mg-104d-7b] DRY-RUN — запись в БД пропущена.")
        return

    if not to_save:
        print("[mg-104d-7b] APPLY: нечего сохранять.")
        return

    with transaction.atomic():
        Recipe.objects.bulk_update(
            to_save, ["kcal", "proteins", "fats", "carbs", "povar_raw"],
            batch_size=500,
        )
    print(f"[mg-104d-7b] APPLY: сохранено рецептов: {len(to_save)}")

    # повторная проверка плотности по тем же id
    ids = [r.id for r in to_save]
    still_bad = 0
    for r in Recipe.objects.filter(id__in=ids).only(
            "id", "kcal", "servings", "servings_normalized", "povar_raw"):
        sn = r.servings_normalized or r.servings or 1
        dw = (r.povar_raw or {}).get("dish_weight_g_calc") or 0
        try:
            dw = float(dw)
        except (TypeError, ValueError):
            continue
        if dw <= 0:
            continue
        d = float(r.kcal) * sn / dw
        if d > DENSITY_LIMIT:
            still_bad += 1
    print(f"[mg-104d-7b] после APPLY: с density>{DENSITY_LIMIT} среди починённых: {still_bad}")


main()
