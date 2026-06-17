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


def _parse_raw_ingredient(raw: str) -> dict:
    """«масло оливковое (2 ст. л.)» -> {name, quantity, unit}."""
    raw = (raw or "").strip()
    name, quantity, unit = raw, "", ""
    m = re.search(r"^(.*?)\s*\(([^)]*)\)\s*$", raw)
    if m:
        name = m.group(1).strip()
        inside = m.group(2).strip()
        num_m = re.match(r"^([\d]+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*(.*)$", inside)
        if num_m:
            quantity = num_m.group(1).replace(",", ".").strip()
            unit = num_m.group(2).strip()
        else:
            unit = inside
    return {"name": name, "quantity": quantity, "unit": unit}


# теги-категории, которые иногда попадают в хвост ингредиентов без «;»
_TAG_MARKERS = (
    "рецепт", "блюда из", "пошаговый", "с фото", "с видео", "вегетариан",
    "на скорую руку", "для детей", "праздничн", "в мультиварке", "в духовке",
    "на сковороде", "на пару", "время приготовления", "затраты времени",
)


def _normalize_ingredients(raw_list: list) -> list:
    """Склеивает raw-список, обрезает по «;», парсит в [{name, quantity, unit}]."""
    raws = []
    for i in raw_list or []:
        if isinstance(i, dict):
            raws.append(i.get("raw") or i.get("name") or "")
        elif isinstance(i, str):
            raws.append(i)
    joined = ", ".join(r for r in raws if r)

    semi = joined.find(";")
    if semi != -1:
        joined = joined[:semi]

    out = []
    for p in re.split(r",\s*(?![^(]*\))", joined):
        p = p.strip().rstrip(".,;").strip()
        if p and len(p) > 1 and not any(m in p.lower() for m in _TAG_MARKERS):
            out.append(_parse_raw_ingredient(p))
    return out


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
                            ingredients=_normalize_ingredients(data.get("ingredients", [])),
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
