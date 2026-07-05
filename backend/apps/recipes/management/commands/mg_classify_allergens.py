"""MG_ALLERGEN14: разметка Recipe.allergens по ингредиентам + названию.

Правиловый классификатор (apps.common.allergens). По умолчанию размечает
только рецепты с пустым allergens; --all — переразметить все.
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from apps.common.allergens import classify_recipe, label_for
from apps.recipes.models import Recipe


class Command(BaseCommand):
    help = "MG_ALLERGEN14: классифицировать аллергены рецептов по ингредиентам"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="ничего не сохранять")
        parser.add_argument("--all", action="store_true", help="переразметить все рецепты (а не только пустые)")
        parser.add_argument("--limit", type=int, default=0, help="ограничить кол-во (отладка)")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        do_all = opts["all"]
        limit = opts["limit"]

        qs = Recipe.objects.all().order_by("id")
        if not do_all:
            # только те, у кого ещё нет разметки
            qs = qs.filter(allergens=[])
        if limit:
            qs = qs[:limit]

        total = 0
        changed = 0
        per_allergen = Counter()

        for r in qs.iterator():
            total += 1
            new = classify_recipe(r)
            for k in new:
                per_allergen[k] += 1
            old = sorted(r.allergens or [])
            if new != old:
                changed += 1
                if not dry:
                    Recipe.objects.filter(pk=r.pk).update(allergens=new)

        self.stdout.write(
            self.style.SUCCESS(f"\n{'DRY-RUN ' if dry else ''}готово. Обработано: {total}. Изменено: {changed}.")
        )
        self.stdout.write("\n— Рецептов с аллергеном:")
        for k, v in per_allergen.most_common():
            self.stdout.write(f"    {label_for(k):26s} {v}")
