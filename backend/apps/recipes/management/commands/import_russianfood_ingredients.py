"""Импорт ингредиентов с количествами из JSON (скрейп russianfood.com).

Матчит рецепт по `source_url` (по `rid`) и заполняет `ingredients` реальным
составом с количествами. Для каждого ингредиента:
  - quantity — исходный текст количества ("800-850 г", "1 стакан", "по вкусу");
  - grams    — число: точно для метрики (г/кг/мл), по таблице типовых весов для
               бытовых единиц (шт/стакан/ложка/зубчик/пучок); "по вкусу" — без grams.

Формат JSON: [{"url": "...rid=NNN", "ingredients": {"Название": "количество", ...}}].

Идемпотентно: рецепт пропускается, если у него УЖЕ есть граммовка (значит уже
обогащён). Перестройку recipe→product связей при сохранении не запускаем —
после импорта запусти mg_backfill_recipe_products для пересчёта связей.

Безопасно: dry-run по умолчанию, запись по --apply, --limit N.

    docker compose exec -T backend python manage.py import_russianfood_ingredients --limit 20
    docker compose exec -T backend python manage.py import_russianfood_ingredients --apply
"""

import json
import os
import re

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

_RID_RE = re.compile(r"rid=(\d+)")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_RANGE_RE = re.compile(r"\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?")

# Типовые веса «штуки» по продукту (граммы). Проверяем вхождение ключа в имя.
_PIECE_G = {
    "яйц": 55,
    "лук": 90,
    "помидор": 120,
    "томат": 120,
    "морков": 85,
    "картофел": 100,
    "картошк": 100,
    "перец болгарск": 150,
    "перец сладк": 150,
    "перец": 60,
    "огурец": 100,
    "яблок": 180,
    "банан": 120,
    "лимон": 100,
    "апельсин": 200,
    "баклажан": 250,
    "кабач": 250,
    "свёкл": 150,
    "свекл": 150,
    "чеснок": 40,  # головка
}
# Типовой вес столовой ложки по продукту (граммы).
_TBSP_G = {
    "масл": 17,
    "сметан": 25,
    "мук": 25,
    "сахар": 20,
    "мёд": 21,
    "мед": 21,
    "крахмал": 12,
    "соус": 18,
    "паст": 20,
}
_TBSP_DEFAULT = 15
_TSP_DEFAULT = 5


def _match_key(name, table, default=None):
    low = (name or "").lower()
    for key, val in table.items():
        if key in low:
            return val
    return default


def _parse_grams(name, qty):
    """Число граммов из текста количества; None если оценить нельзя."""
    s = str(qty).strip().lower().replace(",", ".")
    if not s:
        return None
    if any(w in s for w in ("вкус", "кончик", "щепот")):
        return None
    if not _NUM_RE.search(s):
        return None
    rng = _RANGE_RE.search(s)
    if rng:
        a, b = _NUM_RE.findall(rng.group(0))[:2]
        n = (float(a) + float(b)) / 2.0
    else:
        n = float(_NUM_RE.search(s).group(0))

    if "кг" in s:
        return round(n * 1000)
    if "мл" in s:
        return round(n)
    if re.search(r"ст\.?\s*л", s) or "столов" in s:
        return round(n * _match_key(name, _TBSP_G, _TBSP_DEFAULT))
    if re.search(r"ч\.?\s*л", s) or "чайн" in s:
        return round(n * _TSP_DEFAULT)
    if "стакан" in s:
        return round(n * 200)
    if "зубч" in s:
        return round(n * 5)
    if "пучок" in s or "пучк" in s:
        return round(n * 40)
    if "банк" in s:
        return round(n * 400)
    if "шт" in s:
        return round(n * _match_key(name, _PIECE_G, 80))
    if "литр" in s or re.search(r"(^|\s)л\.?($|\s)", s):
        return round(n * 1000)
    if "грам" in s or re.search(r"(^|\s)г\.?($|\s)", s):
        return round(n)
    return None


def _has_grams(recipe):
    for ing in recipe.ingredients or []:
        if isinstance(ing, dict) and ing.get("grams") not in (None, "", 0):
            return True
    return False


def _default_json_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "russianfood_ingredients.json"
    )


class Command(BaseCommand):
    help = "Импорт ингредиентов с количествами из JSON (russianfood). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать результат (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--file", default=_default_json_path(), help="Путь к JSON (по умолчанию — встроенный).")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        path = opts["file"]

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Не удалось прочитать JSON {path}: {e}"))
            return
        if not isinstance(data, list):
            self.stderr.write(self.style.ERROR("Ожидался JSON-массив."))
            return

        # rid -> recipe (первый по source_url)
        by_rid = {}
        for r in Recipe.objects.exclude(source_url__isnull=True).exclude(source_url="").iterator():
            m = _RID_RE.search(r.source_url)
            if m:
                by_rid.setdefault(m.group(1), r)

        updated = skipped_has = not_found = 0
        rows_total = rows_grams = 0
        samples = []

        for entry in data:
            if limit and updated >= limit:
                break
            if not isinstance(entry, dict):
                continue
            m = _RID_RE.search(entry.get("url", ""))
            ings = entry.get("ingredients") or {}
            if not m or not isinstance(ings, dict) or not ings:
                continue
            recipe = by_rid.get(m.group(1))
            if recipe is None:
                not_found += 1
                continue
            if _has_grams(recipe):
                skipped_has += 1
                continue

            new_ings = []
            g_here = 0
            for name, qty in ings.items():
                name = str(name).strip()
                if not name:
                    continue
                grams = _parse_grams(name, qty)
                rows_total += 1
                if grams is not None:
                    rows_grams += 1
                    g_here += 1
                new_ings.append({"name": name[:255], "quantity": str(qty)[:64], "unit": "", "grams": grams})
            if not new_ings:
                continue

            if len(samples) < 8:
                samples.append(f"  #{recipe.id} {recipe.title[:40]}: {len(new_ings)} ингр., с граммами {g_here}")
            if apply:
                recipe.ingredients = new_ings
                # связи recipe→product пересчитаем отдельно (mg_backfill_recipe_products)
                recipe._mg_skip_link_rebuild = True
                recipe.save(update_fields=["ingredients"])
            updated += 1

        for s in samples:
            self.stdout.write(s)
        cover = (100.0 * rows_grams / rows_total) if rows_total else 0.0
        self.stdout.write(
            f"Обновлено рецептов: {updated}; пропущено (уже с граммами): {skipped_has}; "
            f"не найдено в БД: {not_found}."
        )
        self.stdout.write(f"Ингредиентов: {rows_total}, из них с граммовкой: {rows_grams} ({cover:.0f}%).")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Готово. Рекомендуется: mg_backfill_recipe_products для пересчёта связей и "
                    "fill_recipe_kbju_ai --apply для КБЖУ."
                )
            )
