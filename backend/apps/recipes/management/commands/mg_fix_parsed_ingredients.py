"""
Конвертация ингредиентов формата {raw: "название (кол-во единица)"}
в формат {name, quantity, unit}, который понимает UI.

Применяется к рецептам source='parsed' (импортированные гарниры).

Запуск:
  python manage.py mg_fix_parsed_ingredients            # dry-run
  python manage.py mg_fix_parsed_ingredients --apply
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction


def parse_raw_ingredient(raw: str) -> dict:
    """
    «масло оливковое (2 ст. л.)» -> {name, quantity, unit}
    «соль (по вкусу)»            -> {name:'соль', quantity:'', unit:'по вкусу'}
    «картофель молодой»          -> {name:'картофель молодой', quantity:'', unit:''}
    """
    raw = (raw or "").strip()
    name = raw
    quantity = ""
    unit = ""

    m = re.search(r"^(.*?)\s*\(([^)]*)\)\s*$", raw)
    if m:
        name = m.group(1).strip()
        inside = m.group(2).strip()
        # «2 ст. л.» / «0,5 шт.» / «1 некрупный» / «по вкусу»
        num_m = re.match(r"^([\d]+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*(.*)$", inside)
        if num_m:
            quantity = num_m.group(1).replace(",", ".").strip()
            unit = num_m.group(2).strip()
        else:
            # числа нет: «по вкусу», «по желанию» -> в unit
            unit = inside

    return {"name": name, "quantity": quantity, "unit": unit}


class Command(BaseCommand):
    help = "Конвертирует raw-ингредиенты в {name, quantity, unit} для source='parsed'"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        from apps.recipes.models import Recipe

        apply = options["apply"]
        mode = "APPLY" if apply else "DRY-RUN"

        qs = Recipe.objects.filter(source="parsed")
        self.stdout.write(f"[mg_fix_parsed_ingredients] mode={mode} рецептов: {qs.count()}")

        converted = 0
        skipped = 0
        sample_shown = 0

        to_update = []
        for r in qs.iterator():
            ingr = r.ingredients or []
            if not ingr:
                skipped += 1
                continue
            # уже в новом формате?
            if all(isinstance(i, dict) and "raw" not in i for i in ingr):
                skipped += 1
                continue

            new_ingr = []
            for i in ingr:
                if isinstance(i, dict) and "raw" in i:
                    new_ingr.append(parse_raw_ingredient(i["raw"]))
                else:
                    new_ingr.append(i)

            if sample_shown < 3:
                self.stdout.write(f"\n  «{r.title}»")
                for old, new in zip(ingr[:4], new_ingr[:4]):
                    self.stdout.write(f"    {old}  ->  {new}")
                sample_shown += 1

            r.ingredients = new_ingr
            to_update.append(r)
            converted += 1

        if apply and to_update:
            with transaction.atomic():
                Recipe.objects.bulk_update(to_update, ["ingredients"], batch_size=200)

        self.stdout.write(
            f"\n{'='*50}\n"
            f"Итог [{mode}]:\n"
            f"  Конвертировано: {converted}\n"
            f"  Пропущено:      {skipped}\n"
        )
        if not apply:
            self.stdout.write("DRY-RUN. Запустите с --apply для записи.")
