"""MG_OFFIMG: массовая загрузка фото продуктов из Openverse (CC, без ключа).

Ищем по названию продукта (как есть). Изображения под свободными лицензиями.

Примеры:
    python manage.py fetch_product_images --system-only            # каталог без фото
    python manage.py fetch_product_images --limit 200 --sleep 0.5
    python manage.py fetch_product_images --dry-run                # только показать
    python manage.py fetch_product_images --overwrite              # перезаписать
"""

import time

from django.core.management.base import BaseCommand

from apps.fridge.models import Product
from apps.fridge.services import fetch_openverse_image_url


class Command(BaseCommand):
    help = "Заполнить Product.image_url картинками из Openverse (поиск по названию)."

    def add_arguments(self, parser):
        parser.add_argument("--system-only", action="store_true", help="Только системные продукты (owner is null).")
        parser.add_argument("--overwrite", action="store_true", help="Перезаписывать уже заданные image_url.")
        parser.add_argument("--limit", type=int, default=0, help="Максимум продуктов за прогон (0 — без лимита).")
        parser.add_argument("--sleep", type=float, default=0.5, help="Пауза между запросами, сек.")
        parser.add_argument("--dry-run", action="store_true", help="Только показать, ничего не сохранять.")

    def handle(self, *args, **opts):
        qs = Product.objects.all().order_by("id")
        if opts["system_only"]:
            qs = qs.filter(owner__isnull=True)
        if not opts["overwrite"]:
            qs = (qs.filter(image_url__isnull=True) | qs.filter(image_url="")).distinct()
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        total = qs.count()
        self.stdout.write(f"К обработке продуктов: {total}")
        updated = missed = 0
        for i, p in enumerate(qs, 1):
            img = fetch_openverse_image_url(p.name)
            if img:
                updated += 1
                if opts["dry_run"]:
                    self.stdout.write(f"  [{i}/{total}] {p.name} -> {img}")
                else:
                    p.image_url = img
                    p.save(update_fields=["image_url"])
            else:
                missed += 1
            if opts["sleep"]:
                time.sleep(opts["sleep"])

        prefix = "(dry-run) " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Готово. Обновлено: {updated}, без результата: {missed}."))
