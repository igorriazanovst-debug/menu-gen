"""
MG-104d-5: Нормализация servings/dish_weight_g.

Логика:
1. Считаем dish_weight_g из ingredients_norm (используя density.tsv + pieces_g.tsv + pieces_default_g.tsv).
2. Если dish_weight_g_calc >= 100 г: servings_normalized = max(1, round(dw / SERVING_G)).
3. Иначе fallback по kcal: servings_normalized = max(1, round(kcal_total / TARGET_KCAL_PER_SERVING)).
4. Если |servings_normalized - servings| > 1 — пересчитываем kcal/B/Ж/У на новую порцию.

Запуск:
    docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
      'python manage.py shell < /app/scripts/mg_104d5_normalize_servings.py'

Переменные окружения:
    MG104D5_DRY_RUN=1   — не писать в БД (по умолчанию: 0).
    MG104D5_LIMIT=N     — обработать только N рецептов (для отладки).
    MG104D5_DATA_DIR    — куда писать отчёт (default: /tmp/menugen).
    MG104D5_SERVING_G   — целевая порция в граммах (default: 300).
    MG104D5_TARGET_KCAL — целевая kcal/порцию для fallback (default: 500).
    MG104D5_DELTA       — порог пересчёта по разнице servings (default: 1, т.е. >1 = пересчёт).
"""

import csv
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.db import transaction


DRY_RUN = os.environ.get("MG104D5_DRY_RUN", "0") == "1"
LIMIT = int(os.environ.get("MG104D5_LIMIT", "0"))
DATA_DIR = Path(os.environ.get("MG104D5_DATA_DIR", "/tmp/menugen"))
SERVING_G = float(os.environ.get("MG104D5_SERVING_G", "300"))
TARGET_KCAL = float(os.environ.get("MG104D5_TARGET_KCAL", "500"))
DELTA = int(os.environ.get("MG104D5_DELTA", "1"))
MAX_DW_G = float(os.environ.get("MG104D5_MAX_DW_G", "5000"))  # выше — fallback на by_kcal

REF_DIR = Path("/app/data")  # внутри контейнера = /opt/menugen/backend/data

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = DATA_DIR / "mg_104d5_report.tsv"
SUMMARY_PATH = DATA_DIR / "mg_104d5_summary.txt"


# ---------- helpers ----------

def load_tsv(path: Path) -> dict:
    """Загружает TSV в виде dict[name] -> value (float из 2-й колонки)."""
    out = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        rd = csv.reader(f, delimiter="\t")
        for row in rd:
            if not row or len(row) < 2:
                continue
            if row[0].startswith("#") or row[0].lower() in ("name", "unit_canon", "name_canon"):
                continue
            try:
                out[row[0].strip().lower()] = float(row[1])
            except (ValueError, IndexError):
                continue
    return out


def load_pieces_g(path: Path) -> dict:
    """pieces_g.tsv формат: name_canon\\tunit_canon\\tgrams_per_unit\\tsource. Граммы в 3-й колонке."""
    out = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        rd = csv.reader(f, delimiter="\t")
        for row in rd:
            if not row or len(row) < 3:
                continue
            if row[0].startswith("#") or row[0].lower() in ("name", "name_canon"):
                continue
            try:
                out[row[0].strip().lower()] = float(row[2])
            except (ValueError, IndexError):
                continue
    return out


# regex штучных изделий — порция = штука, не семейная порция
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

# исключения для слов с двойным смыслом (желе/холодец из мяса — банкетное блюдо, не штучное)
UNIT_EXCLUDE_RE = re.compile(
    r"\b("
    r"холодец|заливн|"
    r"желе\s+из\s+(мяс|курин|говяж|свин|рыб|телятин|индейк|утк|баран|язык|петух)|"
    r"мясн(ое|ой)\s+желе|"
    r"рыбн(ое|ой)\s+желе"
    r")",
    re.IGNORECASE,
)


def is_unit_serving(title: str, servings: int, dw_calc: float, kcal_old: float) -> tuple[bool, str]:
    """
    Определяет «штучный» рецепт (servings = штук, не порций).
    Возвращает (флаг, причина).
    """
    t = (title or "").lower()
    # явные исключения (мясное желе/холодец/заливное)
    if UNIT_EXCLUDE_RE.search(t):
        return False, ""
    if UNIT_TITLE_RE.search(t):
        return True, "title_match"
    # признак: много "порций" при малом весе
    if servings >= 12 and 0 < dw_calc < 1500:
        return True, "many_small_servings"
    # признак: высокая удельная калорийность сладкой выпечки
    if kcal_old and servings > 0 and dw_calc > 0:
        density = (float(kcal_old) * int(servings)) / dw_calc
        if density > 6.0 and servings >= 8:
            return True, "high_kcal_density"
    # доп. эвристика: много порций + малый kcal/порция → явно мелкая расфасовка
    if servings >= 16 and 0 < dw_calc < 3000 and kcal_old is not None and kcal_old < 100:
        return True, "low_kcal_many_servings"
    return False, ""


def estimate_grams(ing: dict, density_map: dict, pieces_map: dict, pieces_default: dict) -> float:
    """Оценить массу одного ингредиента в граммах. Возвращает 0 если skip или невалид."""
    if ing.get("skip"):
        return 0.0
    qty = ing.get("quantity")
    if qty is None:
        return 0.0
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return 0.0
    if qty <= 0:
        return 0.0

    unit = (ing.get("unit_canon") or "").strip().lower()
    name = (ing.get("name_canon") or "").strip().lower()

    if unit == "г":
        return qty
    if unit == "кг":
        return qty * 1000.0
    if unit == "мл":
        d = density_map.get(name, 1.0)
        return qty * d
    if unit == "л":
        d = density_map.get(name, 1.0)
        return qty * 1000.0 * d
    if unit == "шт":
        if name in pieces_map:
            return qty * pieces_map[name]
        return qty * pieces_default.get("шт", 100.0)
    # прочие — дефолт по unit_canon
    return qty * pieces_default.get(unit, 0.0)


def calc_dish_weight(povar_raw: dict, density_map, pieces_map, pieces_default) -> float:
    """Сумма граммов по всем ингредиентам."""
    ings = povar_raw.get("ingredients_norm") or []
    total = 0.0
    for ing in ings:
        total += estimate_grams(ing, density_map, pieces_map, pieces_default)
    return round(total, 1)


def normalize_servings(dish_weight_g: float, kcal_per_serving: float, current_servings: int) -> tuple[int, str]:
    """
    Возвращает (servings_normalized, method).
    method: 'by_weight' | 'by_kcal' | 'kept' | 'by_kcal_overflow'
    """
    # верхний санити-лимит: блюдо >MAX_DW_G скорее всего ошибка парсинга → fallback на kcal
    if dish_weight_g > MAX_DW_G and kcal_per_serving and current_servings:
        kcal_total = float(kcal_per_serving) * int(current_servings)
        n = max(1, round(kcal_total / TARGET_KCAL))
        return n, "by_kcal_overflow"
    if dish_weight_g >= 100.0:
        n = max(1, round(dish_weight_g / SERVING_G))
        return n, "by_weight"
    # fallback по kcal
    if kcal_per_serving and current_servings:
        kcal_total = float(kcal_per_serving) * int(current_servings)
        n = max(1, round(kcal_total / TARGET_KCAL))
        return n, "by_kcal"
    return current_servings or 1, "kept"


# ---------- main ----------

def main():
    Recipe = apps.get_model("recipes", "Recipe")

    density_map = load_tsv(REF_DIR / "density.tsv")
    pieces_map = load_pieces_g(REF_DIR / "pieces_g.tsv")
    pieces_default = load_tsv(REF_DIR / "pieces_default_g.tsv")

    print(f"[d-5] DRY_RUN={DRY_RUN} LIMIT={LIMIT} SERVING_G={SERVING_G} TARGET_KCAL={TARGET_KCAL} DELTA={DELTA} MAX_DW_G={MAX_DW_G}")
    print(f"[d-5] density={len(density_map)} pieces={len(pieces_map)} pieces_default={len(pieces_default)}")

    qs = Recipe.objects.exclude(povar_raw__isnull=True).exclude(povar_raw={}).order_by("id")
    if LIMIT > 0:
        qs = qs[:LIMIT]

    stats = {
        "total": 0,
        "by_weight": 0,
        "by_kcal": 0,
        "by_kcal_overflow": 0,
        "unit_kept": 0,
        "kept_suspicious_dw": 0,
        "kept": 0,
        "recalc_kbju": 0,
        "no_change": 0,
        "dw_written": 0,
    }

    rows = []

    for r in qs.iterator(chunk_size=500):
        stats["total"] += 1
        pr = r.povar_raw or {}

        dw_calc = calc_dish_weight(pr, density_map, pieces_map, pieces_default)

        kcal_old = float(r.kcal) if r.kcal is not None else None
        servings_old = int(r.servings or 1)

        # детектор штучных — не трогаем kcal, servings_normalized = servings
        is_unit, unit_reason = is_unit_serving(r.title or "", servings_old, dw_calc, kcal_old)
        if is_unit:
            n_norm = servings_old
            method = f"unit_kept:{unit_reason}"
            stats["unit_kept"] += 1
            recalc = False
        else:
            n_norm, base_method = normalize_servings(dw_calc, kcal_old, servings_old)
            # защита от перенасыщения порций при подозрительном dw_calc:
            # если dw в зоне 3000-5000г И servings_old >= 2 И kcal_old <= 1500
            # И n_norm > servings_old*2 → доверяем исходнику
            if (
                base_method == "by_weight"
                and 3000 <= dw_calc <= 5000
                and servings_old >= 2
                and kcal_old is not None and kcal_old <= 1500
                and n_norm > servings_old * 2
            ):
                n_norm = servings_old
                method = "kept_suspicious_dw"
                stats["kept_suspicious_dw"] += 1
                recalc = False
            else:
                method = base_method
                stats[base_method] += 1
                recalc = abs(n_norm - servings_old) > DELTA

        diff = abs(n_norm - servings_old)

        kcal_new = kcal_old
        prot_new = float(r.proteins) if r.proteins is not None else None
        fat_new = float(r.fats) if r.fats is not None else None
        carb_new = float(r.carbs) if r.carbs is not None else None

        if recalc and kcal_old is not None and servings_old > 0 and n_norm > 0:
            scale = servings_old / n_norm  # умножаем kcal_per_serving на scale
            kcal_new = round(kcal_old * scale, 1)
            if r.proteins is not None:
                prot_new = round(float(r.proteins) * scale, 1)
            if r.fats is not None:
                fat_new = round(float(r.fats) * scale, 1)
            if r.carbs is not None:
                carb_new = round(float(r.carbs) * scale, 1)
            stats["recalc_kbju"] += 1
        else:
            stats["no_change"] += 1

        rows.append({
            "id": r.id,
            "title": (r.title or "")[:80],
            "servings_old": servings_old,
            "servings_normalized": n_norm,
            "diff": diff,
            "method": method,
            "dw_calc_g": dw_calc,
            "kcal_old": kcal_old,
            "kcal_new": kcal_new if recalc else "",
            "recalc": "yes" if recalc else "no",
        })

        if not DRY_RUN:
            with transaction.atomic():
                pr["dish_weight_g_calc"] = dw_calc
                r.povar_raw = pr
                r.servings_normalized = n_norm
                if recalc:
                    r.kcal = Decimal(str(kcal_new)) if kcal_new is not None else None
                    if prot_new is not None:
                        r.proteins = Decimal(str(prot_new))
                    if fat_new is not None:
                        r.fats = Decimal(str(fat_new))
                    if carb_new is not None:
                        r.carbs = Decimal(str(carb_new))
                update_fields = ["povar_raw", "servings_normalized"]
                if recalc:
                    update_fields += ["kcal", "proteins", "fats", "carbs"]
                r.save(update_fields=update_fields)
            stats["dw_written"] += 1

        if stats["total"] % 500 == 0:
            print(f"  ...processed {stats['total']}")

    # отчёт
    with REPORT_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t") if rows else None
        if w:
            w.writeheader()
            w.writerows(rows)

    # топ изменений (по diff)
    top_changes = sorted([r for r in rows if r["recalc"] == "yes"], key=lambda x: x["diff"], reverse=True)[:30]

    summary_lines = [
        f"MG-104d-5 summary",
        f"DRY_RUN={DRY_RUN} SERVING_G={SERVING_G} TARGET_KCAL={TARGET_KCAL} DELTA={DELTA} MAX_DW_G={MAX_DW_G}",
        "",
        f"total processed:     {stats['total']}",
        f"  by_weight:         {stats['by_weight']}",
        f"  by_kcal:           {stats['by_kcal']}",
        f"  by_kcal_overflow:  {stats['by_kcal_overflow']}  (dw>{MAX_DW_G:.0f}, fallback)",
        f"  unit_kept:         {stats['unit_kept']}  (штучные изделия — не пересчитываем)",
        f"  kept_suspicious_dw:{stats['kept_suspicious_dw']}  (dw 3-5кг и kcal_old<=1500 — доверяем исходнику)",
        f"  kept (no data):    {stats['kept']}",
        "",
        f"recalculated KBJU:   {stats['recalc_kbju']}",
        f"no change (diff<={DELTA}): {stats['no_change']}",
        f"written to DB:       {stats['dw_written']}",
        "",
        "TOP-30 changes (by |servings_old - servings_normalized|):",
        f"  {'id':>6}  {'old':>3}  {'new':>3}  {'diff':>4}  {'method':<22}  {'dw_g':>8}  {'kcal_old':>9}  {'kcal_new':>9}  title",
    ]
    for row in top_changes:
        summary_lines.append(
            f"  {row['id']:>6}  {row['servings_old']:>3}  {row['servings_normalized']:>3}  "
            f"{row['diff']:>4}  {row['method']:<22}  {row['dw_calc_g']:>8.1f}  "
            f"{(row['kcal_old'] or 0):>9.1f}  {(row['kcal_new'] or 0):>9}  {row['title']}"
        )

    summary = "\n".join(summary_lines)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print()
    print(summary)
    print()
    print(f"[d-5] report:  {REPORT_PATH}")
    print(f"[d-5] summary: {SUMMARY_PATH}")


main()
