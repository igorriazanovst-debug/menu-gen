"""Кардинальная чистка рецептов-импортов с russianfood.

Действия (по --apply; по умолчанию dry-run только считает):
  1) УДАЛИТЬ рецепты с source_url на russianfood, у которых НЕТ полного КБЖУ
     (отсутствует хотя бы одно из калорий/белков/жиров/углеводов).
  2) У ОСТАВШИХСЯ russianfood-рецептов (с полным КБЖУ) очистить source_url
     (убрать ссылку на russianfood).

ВНИМАНИЕ: удаление каскадно уносит связанные menu.MenuItem (on_delete=CASCADE) —
то есть эти блюда исчезнут из уже сгенерированных меню. Diary-записи не удаляются
(SET_NULL: recipe становится пустым, запись остаётся). Операция необратима —
ПЕРЕД --apply сделай бэкап БД (deploy_backend.sh это делает автоматически, либо
pg_dump вручную).

    docker compose exec -T backend python manage.py purge_russianfood_recipes           # dry-run
    docker compose exec -T backend python manage.py purge_russianfood_recipes --apply
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.models import Recipe

from .fill_recipe_kbju_ai import _needs_kbju


class Command(BaseCommand):
    help = "Удалить russianfood-рецепты без КБЖУ и снять ссылки у остальных. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить (иначе dry-run).")

    def handle(self, *args, **opts):
        apply = opts["apply"]

        rf = (
            Recipe.objects.filter(source_url__icontains="russianfood")
            .exclude(source_url__isnull=True)
            .exclude(source_url="")
        )
        total_rf = rf.count()

        to_delete_ids = []
        keep_ids = []
        for r in rf.only("id", "nutrition").iterator():
            if _needs_kbju(r):
                to_delete_ids.append(r.id)
            else:
                keep_ids.append(r.id)

        # Каскадное влияние на меню
        try:
            from apps.menu.models import MenuItem

            menu_items = MenuItem.objects.filter(recipe_id__in=to_delete_ids).count()
        except Exception:
            menu_items = -1

        self.stdout.write(f"russianfood-рецептов всего: {total_rf}")
        self.stdout.write(f"  УДАЛИТЬ (без полного КБЖУ):        {len(to_delete_ids)}")
        self.stdout.write(f"  ОСТАВИТЬ + снять ссылку (с КБЖУ):  {len(keep_ids)}")
        self.stdout.write(
            f"  каскадно удалится MenuItem'ов:     {menu_items}"
            if menu_items >= 0
            else "  MenuItem: посчитать не удалось"
        )

        # примеры к удалению
        for r in Recipe.objects.filter(id__in=to_delete_ids[:8]).only("id", "title"):
            self.stdout.write(f"    - #{r.id} {r.title[:55]}")

        if not apply:
            self.stdout.write(
                self.style.WARNING("DRY-RUN — ничего не изменено. Для выполнения: --apply (сделай бэкап!).")
            )
            return

        with transaction.atomic():
            cleared = Recipe.objects.filter(id__in=keep_ids).update(source_url="")
            deleted, per_model = Recipe.objects.filter(id__in=to_delete_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Готово. Удалено рецептов+связей: {deleted}; снято ссылок: {cleared}."))
        for model, cnt in sorted(per_model.items()):
            self.stdout.write(f"    {model}: {cnt}")
