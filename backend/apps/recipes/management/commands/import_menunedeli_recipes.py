"""Импорт НОВЫХ рецептов из JSON (menunedeli.ru).

Формат записи:
  {
    "url": "...", "title": "...",
    "ingredients": ["Название – 1 кг", "Соль – по вкусу", ...],
    "bju_per_100g": {"Калории": "170", "Белки": "..", "Жиры": "..", "Углеводы": ".."},
    "portion_size": "8порций", "active_time": "15 минут",
    "steps": ["шаг1", "шаг2", ...]
  }

Создаёт рецепты (source=import, is_published=True). Раскладывает:
  - ingredients -> [{name, quantity, unit, grams}] (grams: метрика точно +
    эвристика для шт/стакан/ложка/зубчик/пучок, "по вкусу" — без grams);
  - bju_per_100g -> nutrition (Калории/Белки/Жиры/Углеводы -> calories/…) +
    числовые поля per-100g;
  - portion_size -> servings; active_time -> cook_time/cook_time_min;
  - steps -> [{text, order}].

Идемпотентно: рецепт с таким source_url повторно не создаётся. Связи
recipe→product при создании не строим (потом mg_backfill_recipe_products).
Аллергены проставляются автоматически (Recipe.save -> classify_recipe).
У кого нет полного КБЖУ — добить потом fill_recipe_kbju_ai.

Безопасно: dry-run по умолчанию, запись по --apply, --limit N.

    docker compose exec -T backend python manage.py import_menunedeli_recipes --limit 5
    docker compose exec -T backend python manage.py import_menunedeli_recipes --apply
"""

import json
import os
import re

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

from .import_russianfood_ingredients import _parse_grams
from .scrape_russianfood_ingredients import _parse_ingredient_line

# Русские ключи КБЖУ -> ключи nutrition (плоский, на 100 г)
_BJU_MAP = {"Калории": "calories", "Белки": "proteins", "Жиры": "fats", "Углеводы": "carbs"}
_NUM_FIELD = {
    "calories": "kcal_per_100g",
    "proteins": "proteins_per_100g",
    "fats": "fats_per_100g",
    "carbs": "carbs_per_100g",
}


def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _int_lead(v):
    m = re.search(r"\d+", str(v or ""))
    return int(m.group(0)) if m else None


def _default_json_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "seed", "menunedeli_recipes.json")


class Command(BaseCommand):
    help = "Импорт новых рецептов из JSON (menunedeli). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Создать не более N рецептов (0 = все).")
        parser.add_argument("--file", default=_default_json_path(), help="Путь к JSON (по умолчанию — встроенный).")

    def _build(self, entry):
        title = (entry.get("title") or "").strip()
        url = (entry.get("url") or "").strip()
        if not title:
            return None

        ings = []
        g_rows = 0
        for line in entry.get("ingredients") or []:
            parsed = _parse_ingredient_line(str(line))
            if not parsed["name"]:
                continue
            q, u = parsed["quantity"], parsed["unit"]
            grams = _parse_grams(parsed["name"], (q + " " + u).strip())
            if grams is not None:
                g_rows += 1
            ings.append({"name": parsed["name"][:255], "quantity": q[:64], "unit": u[:50], "grams": grams})

        nutrition = {}
        b = entry.get("bju_per_100g") or {}
        if isinstance(b, dict):
            for ru, key in _BJU_MAP.items():
                val = _num(b.get(ru))
                if val is not None:
                    nutrition[key] = val

        steps = []
        for i, s in enumerate(entry.get("steps") or [], 1):
            s = str(s).strip()
            if s:
                steps.append({"text": s, "order": i})

        recipe = Recipe(
            title=title[:512],
            source_url=url[:1024],
            source="import",
            is_published=True,
            ingredients=ings,
            steps=steps,
            nutrition=nutrition,
            servings=_int_lead(entry.get("portion_size")),
            cook_time=(entry.get("active_time") or "")[:64] or None,
            cook_time_min=_int_lead(entry.get("active_time")),
        )
        # числовые поля per-100g из nutrition
        for key, field in _NUM_FIELD.items():
            if key in nutrition:
                setattr(recipe, field, nutrition[key])
        return recipe, g_rows, len(ings)

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

        existing = set(
            Recipe.objects.exclude(source_url__isnull=True).exclude(source_url="").values_list("source_url", flat=True)
        )

        created = skipped = 0
        rows_total = rows_grams = 0
        samples = []

        for entry in data:
            if limit and created >= limit:
                break
            if not isinstance(entry, dict):
                continue
            url = (entry.get("url") or "").strip()
            if url and url in existing:
                skipped += 1
                continue
            built = self._build(entry)
            if not built:
                continue
            recipe, g_rows, n_ings = built
            rows_total += n_ings
            rows_grams += g_rows
            if len(samples) < 8:
                cal = recipe.nutrition.get("calories")
                samples.append(f"  + {recipe.title[:42]}: {n_ings} ингр (грамм {g_rows}), {cal} ккал/100г")
            if apply:
                recipe._mg_skip_link_rebuild = True
                recipe.save()  # allergens классифицируются в save()
                existing.add(url)
            created += 1

        for s in samples:
            self.stdout.write(s)
        cover = (100.0 * rows_grams / rows_total) if rows_total else 0.0
        self.stdout.write(f"Создано: {created}; пропущено (уже есть source_url): {skipped}.")
        self.stdout.write(f"Ингредиентов: {rows_total}, с граммовкой: {rows_grams} ({cover:.0f}%).")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не создано. Для записи: --apply"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Готово. Далее: mg_backfill_recipe_products, классификаторы "
                    "(classify_food_group / mg_seed_plate) и fill_recipe_kbju_ai --apply."
                )
            )
