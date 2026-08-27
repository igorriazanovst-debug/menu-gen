"""MG_RECIPESYNC: импорт рецептов из JSON, выгруженного ``export_recipes``.

Идемпотентно: рецепт опознаётся по legacy_id → source_url → нормализованному
названию. Уже существующие пропускаются (или обновляются с ``--update``).
Связи с продуктами пересобираются по именам продуктов целевой базы, поэтому
чужие id из исходной базы сюда не попадают.

Запуск:
    python manage.py import_recipes_json /tmp/recipes.json --dry-run
    python manage.py import_recipes_json /tmp/recipes.json
    python manage.py import_recipes_json /tmp/recipes.json --create-products
    python manage.py import_recipes_json /tmp/recipes.json --update

Картинки: image_url переносится как есть. Если это локальный путь
(/media/...), файл нужно скопировать отдельно — команда посчитает такие.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Служебные ключи, которых нет среди полей модели.
NON_MODEL_KEYS = {"product_links"}


def norm_title(value: str) -> str:
    """Нормализация названия для сопоставления: регистр, ё→е, пробелы, хвостовая пунктуация."""
    s = (value or "").strip().lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:-—–")


def norm_product(value: str) -> str:
    s = (value or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", s)


class Command(BaseCommand):
    help = "MG_RECIPESYNC: импортирует рецепты из JSON (export_recipes), пропуская уже существующие."

    def add_arguments(self, parser):
        parser.add_argument("json_file", help="Путь к JSON-файлу от export_recipes")
        parser.add_argument("--dry-run", action="store_true", default=False, help="Ничего не писать, только отчёт")
        parser.add_argument(
            "--update",
            action="store_true",
            default=False,
            help="Обновлять поля уже существующих рецептов (по умолчанию пропускать)",
        )
        parser.add_argument(
            "--create-products",
            action="store_true",
            default=False,
            help="Создавать отсутствующие продукты рубрикатора (иначе связь останется без product)",
        )
        parser.add_argument("--limit", type=int, default=None, help="Импортировать не больше N рецептов")

    # ── подготовка индексов ──────────────────────────────────────────────────
    def _load_indexes(self):
        from apps.fridge.models import Product, ProductCategory
        from apps.recipes.models import Recipe

        by_legacy: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_title: dict[str, int] = {}
        for pk, legacy_id, source_url, title in Recipe.objects.values_list("id", "legacy_id", "source_url", "title"):
            if legacy_id:
                by_legacy.setdefault(str(legacy_id), pk)
            if source_url:
                by_source.setdefault(source_url.strip(), pk)
            key = norm_title(title)
            if key:
                by_title.setdefault(key, pk)

        products: dict[str, int] = {}
        for pk, name in Product.objects.values_list("id", "name"):
            key = norm_product(name)
            if key:
                products.setdefault(key, pk)

        categories = {slug: pk for pk, slug in ProductCategory.objects.values_list("id", "slug")}
        return by_legacy, by_source, by_title, products, categories

    def _find_existing(self, data, by_legacy, by_source, by_title):
        legacy = (data.get("legacy_id") or "").strip()
        if legacy and legacy in by_legacy:
            return by_legacy[legacy]
        source_url = (data.get("source_url") or "").strip()
        if source_url and source_url in by_source:
            return by_source[source_url]
        return by_title.get(norm_title(data.get("title") or ""))

    # ── связи с продуктами ───────────────────────────────────────────────────
    def _rebuild_links(self, recipe, links, products, categories, create_products, stats):
        from apps.fridge.models import Product
        from apps.recipes.models import RecipeProduct

        RecipeProduct.objects.filter(recipe=recipe).delete()
        rows = []
        for link in links or []:
            product_id = None
            name = link.get("product_name")
            if name:
                key = norm_product(name)
                product_id = products.get(key)
                if product_id is None and create_products:
                    cat_slug = (link.get("product_category_slug") or "").strip()
                    product = Product.objects.create(
                        name=name.strip(),
                        category_fk_id=categories.get(cat_slug),
                        source="import",
                    )
                    products[key] = product.id
                    product_id = product.id
                    stats["products_created"] += 1
                elif product_id is None:
                    stats["products_missing"] += 1

            rows.append(
                RecipeProduct(
                    recipe=recipe,
                    product_id=product_id,
                    category_fk_id=categories.get((link.get("category_slug_fk") or "").strip()),
                    name_raw=link.get("name_raw") or "",
                    name_canonical=link.get("name_canonical") or "",
                    category_slug=link.get("category_slug") or "",
                    quantity=link.get("quantity") or "",
                    unit=link.get("unit") or "",
                    grams=link.get("grams"),
                )
            )
        if rows:
            RecipeProduct.objects.bulk_create(rows)
        stats["links"] += len(rows)

    # ── основной проход ──────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        from apps.recipes.models import Recipe

        path = Path(opts["json_file"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        recipes_data = payload.get("recipes") if isinstance(payload, dict) else payload
        if not isinstance(recipes_data, list):
            raise CommandError("Неожиданный формат файла: ожидался {'recipes': [...]} или список рецептов.")
        if opts["limit"]:
            recipes_data = recipes_data[: opts["limit"]]

        dry_run = opts["dry_run"]
        mode = "DRY-RUN" if dry_run else "APPLY"
        self.stdout.write(f"[import_recipes_json] mode={mode} файл={path} рецептов в файле={len(recipes_data)}")

        by_legacy, by_source, by_title, products, categories = self._load_indexes()
        model_fields = {f.name for f in Recipe._meta.concrete_fields} - {"id"}

        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "links": 0,
            "products_created": 0,
            "products_missing": 0,
            "local_images": 0,
        }

        for data in recipes_data:
            title = (data.get("title") or "").strip()
            if not title:
                stats["failed"] += 1
                continue

            existing_id = self._find_existing(data, by_legacy, by_source, by_title)
            if existing_id and not opts["update"]:
                stats["skipped"] += 1
                continue

            fields = {k: v for k, v in data.items() if k in model_fields and k not in NON_MODEL_KEYS}
            fields["title"] = title
            img = (fields.get("image_url") or "").strip()
            if img and not img.lower().startswith(("http://", "https://")):
                stats["local_images"] += 1

            action = "UPDATE" if existing_id else "CREATE"
            self.stdout.write(f"  {action} «{title[:60]}» связей={len(data.get('product_links') or [])}")
            if dry_run:
                stats["updated" if existing_id else "created"] += 1
                stats["links"] += len(data.get("product_links") or [])
                continue

            try:
                with transaction.atomic():
                    if existing_id:
                        recipe = Recipe.objects.get(pk=existing_id)
                        for key, value in fields.items():
                            setattr(recipe, key, value)
                        # MG_RECIPELINK: гасим post_save-пересборку связей — иначе она
                        # заново разбирает ингредиенты (в т.ч. через ИИ) и перетирает
                        # то, что мы переносим готовым из исходной базы.
                        recipe._mg_skip_link_rebuild = True
                        recipe.save()
                        stats["updated"] += 1
                    else:
                        recipe = Recipe(**fields)
                        recipe._mg_skip_link_rebuild = True
                        recipe.save()
                        stats["created"] += 1
                        # чтобы повторный запуск в том же процессе не создал дубль
                        by_title.setdefault(norm_title(title), recipe.id)
                        if fields.get("legacy_id"):
                            by_legacy.setdefault(str(fields["legacy_id"]), recipe.id)
                        if fields.get("source_url"):
                            by_source.setdefault(str(fields["source_url"]).strip(), recipe.id)
                    self._rebuild_links(
                        recipe,
                        data.get("product_links"),
                        products,
                        categories,
                        opts["create_products"],
                        stats,
                    )
            except Exception as exc:  # noqa: BLE001 — одна плохая запись не должна валить импорт
                self.stderr.write(f"    ошибка на «{title[:60]}»: {exc}")
                stats["failed"] += 1

        self.stdout.write(
            "\n" + "=" * 60 + f"\nИтог [{mode}]:\n"
            f"  Создано рецептов:   {stats['created']}\n"
            f"  Обновлено:          {stats['updated']}\n"
            f"  Пропущено (есть):   {stats['skipped']}\n"
            f"  Ошибок:             {stats['failed']}\n"
            f"  Связей с продуктами:{stats['links']}\n"
            f"  Создано продуктов:  {stats['products_created']}\n"
            f"  Продуктов не нашли: {stats['products_missing']}\n"
        )
        if stats["products_missing"] and not opts["create_products"]:
            self.stdout.write("Часть связей осталась без product — перезапустите с --create-products.")
        if stats["local_images"]:
            self.stdout.write(
                f"У {stats['local_images']} импортируемых рецептов картинки локальные (/media/...) — "
                "скопируйте файлы media/ с исходного сервера, иначе будут битые изображения."
            )
        if dry_run:
            self.stdout.write("Режим DRY-RUN: ничего не записано.")
