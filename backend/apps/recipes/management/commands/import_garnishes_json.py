"""
Импорт гарниров из JSON-файла (собранного scrape_russianfood_local.py).

Запуск:
  python manage.py import_garnishes_json /path/to/garnishes.json
  python manage.py import_garnishes_json /path/to/garnishes.json --dry-run
  python manage.py import_garnishes_json /path/to/garnishes.json --skip-existing
"""

from __future__ import annotations

import json
import logging
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)


def _guess_food_group(title: str) -> str:
    t = title.lower()
    grain_kw = (
        "рис", "гречк", "пшен", "булгур", "кускус", "макарон", "паст", "спагетти",
        "лапш", "перловк", "овсян", "чечевиц", "горох", "фасол", "нут", "полент",
        "ячмен", "пшениц", "киноа", "кукуруз",
    )
    veg_kw = (
        "картофел", "картошк", "капуст", "цветная", "брокколи", "морков",
        "свекл", "тыкв", "кабачк", "баклажан", "цуккин", "помидор", "томат",
        "огурц", "перец", "шпинат", "спаржа", "артишок", "фенхель", "сельдер",
        "репа", "пастернак", "батат", "авокадо", "грибы", "гриб",
    )
    for kw in grain_kw:
        if kw in t:
            return "grain"
    for kw in veg_kw:
        if kw in t:
            return "vegetable"
    return "grain"


class Command(BaseCommand):
    help = "Импортирует гарниры из JSON-файла (собранного scrape_russianfood_local.py)"

    def add_arguments(self, parser):
        parser.add_argument("json_file", help="Путь к JSON-файлу с рецептами")
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--skip-existing", action="store_true", default=True)

    def handle(self, *args, **options):
        from apps.recipes.models import Recipe

        json_path = Path(options["json_file"])
        if not json_path.exists():
            raise CommandError(f"Файл не найден: {json_path}")

        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]
        mode = "DRY-RUN" if dry_run else "APPLY"

        self.stdout.write(f"[import_garnishes_json] mode={mode} файл={json_path}")

        recipes_data: list[dict] = json.loads(json_path.read_text(encoding="utf-8"))
        self.stdout.write(f"Рецептов в файле: {len(recipes_data)}")

        existing_urls: set[str] = set()
        if skip_existing:
            existing_urls = set(
                Recipe.objects.filter(source_url__isnull=False)
                .values_list("source_url", flat=True)
            )
            self.stdout.write(f"Уже в БД: {len(existing_urls)}")

        saved = skipped = failed = 0
        t0 = time.time()

        for i, data in enumerate(recipes_data, 1):
            url = data.get("source_url", "")
            title = data.get("title", "").strip()

            if not title:
                failed += 1
                continue

            if url and url in existing_urls:
                skipped += 1
                continue

            food_group = _guess_food_group(title)

            self.stdout.write(
                f"  [{i}/{len(recipes_data)}] «{title}» | "
                f"ингр={len(data.get('ingredients', []))} | "
                f"шаги={len(data.get('steps', []))} | "
                f"food_group={food_group}"
            )

            if not dry_run:
                try:
                    with transaction.atomic():
                        Recipe.objects.create(
                            title=title,
                            source_url=url or None,
                            image_url=data.get("image_url") or None,
                            cook_time=data.get("cook_time") or "",
                            cook_time_min=data.get("cook_time_min") or None,
                            servings=data.get("servings") or None,
                            ingredients=data.get("ingredients", []),
                            steps=data.get("steps", []),
                            nutrition={},
                            categories=[],
                            dish_type="side",
                            food_group=food_group,
                            is_published=True,
                            is_custom=False,
                            source="parsed",
                        )
                        saved += 1
                except Exception as exc:
                    logger.error("Ошибка сохранения «%s»: %s", title, exc)
                    failed += 1
            else:
                saved += 1

        elapsed = time.time() - t0
        self.stdout.write(
            f"\n{'='*60}\n"
            f"Итог [{mode}] за {elapsed:.0f}с:\n"
            f"  В файле:    {len(recipes_data)}\n"
            f"  Пропущено:  {skipped}\n"
            f"  Сохранено:  {saved}\n"
            f"  Ошибок:     {failed}\n"
        )

        if dry_run:
            self.stdout.write("Режим DRY-RUN. Запустите без --dry-run для записи.")
        else:
            self.stdout.write(
                "\nПосле импорта запустите разметку plate_component:\n"
                "  python manage.py mg_seed_plate --dry-run\n"
                "  python manage.py mg_seed_plate --apply"
            )
