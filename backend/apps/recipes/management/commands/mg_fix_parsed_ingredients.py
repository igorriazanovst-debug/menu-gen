"""
Чинит ингредиенты импортированных гарниров (source='parsed').

Старый скрапер брал список из <meta description> после «состав:», но НЕ обрезал
по «;» — после точки с запятой в описании идут теги-категории («Рецепты вторых
блюд», «Гарниры», «Каши» и т.п.), которые попали в ингредиенты как мусор.

Эта команда: склеивает raw-список обратно в строку, обрезает по первому «;»,
заново разбивает по запятым (с учётом скобок) и парсит в {name, quantity, unit}.

Запуск:
  python manage.py mg_fix_parsed_ingredients            # dry-run
  python manage.py mg_fix_parsed_ingredients --apply
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

# теги-категории, которые иногда оказываются в хвосте без «;»
_TAG_MARKERS = (
    "рецепт", "блюда из", "пошаговый", "с фото", "с видео", "вегетариан",
    "на скорую руку", "для детей", "праздничн", "в мультиварке", "в духовке",
    "на сковороде", "на пару", "время приготовления", "затраты времени",
)


def _is_tag(s: str) -> bool:
    low = s.lower()
    return any(m in low for m in _TAG_MARKERS)


def _parse_one(raw: str) -> dict:
    """«масло подсолнечное (3 ст. ложки)» -> {name, quantity, unit}."""
    raw = (raw or "").strip().rstrip(".,;").strip()
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


def clean_ingredients(raw_list: list) -> list:
    """Склеивает raw-список, обрезает по «;», перепарсит в {name,quantity,unit}."""
    # собрать исходные строки
    raws = []
    for i in raw_list or []:
        if isinstance(i, dict):
            raws.append(i.get("raw") or i.get("name") or "")
        elif isinstance(i, str):
            raws.append(i)
    joined = ", ".join(r for r in raws if r)

    # обрезать по первому «;» — дальше идут теги
    semi = joined.find(";")
    if semi != -1:
        joined = joined[:semi]

    # разбить по запятым, не трогая запятые внутри скобок
    parts = re.split(r",\s*(?![^(]*\))", joined)
    out = []
    for p in parts:
        p = p.strip().rstrip(".,;").strip()
        if p and len(p) > 1 and not _is_tag(p):
            out.append(_parse_one(p))
    return out


class Command(BaseCommand):
    help = "Чинит ингредиенты гарниров source='parsed' (обрезка по «;» + {name,quantity,unit})"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        from apps.recipes.models import Recipe

        apply = options["apply"]
        mode = "APPLY" if apply else "DRY-RUN"

        qs = Recipe.objects.filter(source="parsed")
        self.stdout.write(f"[mg_fix_parsed_ingredients] mode={mode} рецептов: {qs.count()}")

        fixed = 0
        skipped = 0
        sample = 0
        to_update = []

        for r in qs.iterator():
            old = r.ingredients or []
            if not old:
                skipped += 1
                continue

            new = clean_ingredients(old)
            if not new:
                skipped += 1
                continue

            if sample < 4:
                self.stdout.write(f"\n  «{r.title}»  ({len(old)} -> {len(new)})")
                for n in new[:6]:
                    q = f"{n['quantity']} {n['unit']}".strip()
                    self.stdout.write(f"    • {n['name']}  [{q}]")
                sample += 1

            r.ingredients = new
            to_update.append(r)
            fixed += 1

        if apply and to_update:
            with transaction.atomic():
                Recipe.objects.bulk_update(to_update, ["ingredients"], batch_size=200)

        self.stdout.write(
            f"\n{'='*50}\n"
            f"Итог [{mode}]:\n"
            f"  Исправлено: {fixed}\n"
            f"  Пропущено:  {skipped}\n"
        )
        if not apply:
            self.stdout.write("DRY-RUN. Запустите с --apply для записи.")
