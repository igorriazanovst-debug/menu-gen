"""MG_RECIPESYNC: выгрузка рецептов в JSON для переноса между серверами.

Зачем не ``dumpdata``: обычный дамп переносит записи вместе с ``id``, а на
целевом сервере эти id уже заняты другими рецептами и продуктами — данные
перемешались бы. Здесь всё пишется с «натуральными ключами»: рецепт
опознаётся по legacy_id / source_url / названию, связи с продуктами — по
именам продуктов и slug'ам категорий.

Запуск:
    python manage.py export_recipes --output /tmp/recipes.json
    python manage.py export_recipes --output /tmp/recipes.json --include-custom

Парный импорт: ``python manage.py import_recipes_json /tmp/recipes.json``.
Картинки (image_url вида /media/...) файлами не переносятся — их нужно
скопировать отдельно (rsync каталога media/), команда напомнит об этом.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

# Поля, которые не переносим: id — на приёмнике свой, author — своя таблица
# пользователей, даты выставит сама БД.
SKIP_FIELDS = {"id", "author", "created_at", "updated_at"}

EXPORT_VERSION = 1


def recipe_to_dict(recipe) -> dict:
    """Рецепт → словарь простых значений (Decimal/date уйдут в строки при json.dumps)."""
    from apps.recipes.models import Recipe

    data = {}
    for field in Recipe._meta.concrete_fields:
        if field.name in SKIP_FIELDS:
            continue
        data[field.name] = field.value_from_object(recipe)

    links = []
    for link in recipe.product_links.all():
        links.append(
            {
                "product_name": link.product.name if link.product_id else None,
                "product_category_slug": (
                    link.product.category_fk.slug if link.product_id and link.product.category_fk_id else ""
                ),
                "category_slug_fk": link.category_fk.slug if link.category_fk_id else "",
                "name_raw": link.name_raw,
                "name_canonical": link.name_canonical,
                "category_slug": link.category_slug,
                "quantity": link.quantity,
                "unit": link.unit,
                "grams": link.grams,
            }
        )
    data["product_links"] = links
    return data


class Command(BaseCommand):
    help = "MG_RECIPESYNC: выгружает рецепты в JSON с натуральными ключами (для переноса dev → prod)."

    def add_arguments(self, parser):
        parser.add_argument("--output", "-o", required=True, help="Путь к JSON-файлу для записи")
        parser.add_argument(
            "--include-custom",
            action="store_true",
            default=False,
            help="Включать пользовательские рецепты (is_custom=True / с автором). По умолчанию нет.",
        )
        parser.add_argument(
            "--include-unpublished",
            action="store_true",
            default=False,
            help="Включать неопубликованные (is_published=False). По умолчанию нет.",
        )
        parser.add_argument("--limit", type=int, default=None, help="Ограничить число рецептов (для проверки)")

    def handle(self, *args, **opts):
        from apps.recipes.models import Recipe

        out_path = Path(opts["output"])
        if out_path.parent and not out_path.parent.exists():
            raise CommandError(f"Каталог не найден: {out_path.parent}")

        qs = Recipe.objects.all().prefetch_related("product_links__product__category_fk", "product_links__category_fk")
        if not opts["include_custom"]:
            qs = qs.filter(is_custom=False, author__isnull=True)
        if not opts["include_unpublished"]:
            qs = qs.filter(is_published=True)
        qs = qs.order_by("id")
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        recipes = []
        links_total = 0
        local_images = 0
        for recipe in qs.iterator(chunk_size=200) if not opts["limit"] else qs:
            data = recipe_to_dict(recipe)
            links_total += len(data["product_links"])
            img = (data.get("image_url") or "").strip()
            if img and not img.lower().startswith(("http://", "https://")):
                local_images += 1
            recipes.append(data)

        payload = {
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(recipes),
            "recipes": recipes,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")

        size_mb = out_path.stat().st_size / 1024 / 1024
        self.stdout.write(
            self.style.SUCCESS(
                f"Выгружено рецептов: {len(recipes)}, связей с продуктами: {links_total}\n"
                f"Файл: {out_path} ({size_mb:.1f} МБ)"
            )
        )
        if local_images:
            self.stdout.write(
                f"Внимание: у {local_images} рецептов картинки лежат локально (/media/...). "
                "Не забудьте скопировать каталог media/ на целевой сервер."
            )
