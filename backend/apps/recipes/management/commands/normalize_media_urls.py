"""Нормализация абсолютных ссылок на медиа старого сервера → относительные.

При переезде часть URL-полей в БД хранит абсолютные ссылки на старый хост,
например ``http://31.192.110.121:8003/media/recipes/images/x.png``. На новом
сервере страница отдаётся по HTTPS, и такие http-ссылки блокируются браузером
(mixed-content), хотя тот же файл доступен по ``https://menugen.ru/media/...``.

Команда срезает префикс старого хоста, оставляя относительный путь
(``/media/...``). Сериализаторы затем сами подставят ``BACKEND_PUBLIC_URL``.
Ссылки на другие (внешние) хосты не трогаются.

Хосты задаются через --host (можно несколько) или env ``LEGACY_MEDIA_HOSTS``
(через запятую). По умолчанию — прежний IP проекта.

Сухой прогон по умолчанию; запись — с флагом --apply.
Вызывается также из deploy/migrate/import_new.sh после восстановления дампа.
"""

import os
import re

from django.apps import apps
from django.core.management.base import BaseCommand

# (app_label, model_name, [fields]) — где могут быть абсолютные ссылки.
TARGETS = [
    ("recipes", "Recipe", ["image_url", "video_url"]),
    ("fridge", "FridgeItem", ["image_url"]),
    ("shopping", "ShoppingListItem", ["image_url"]),
    ("users", "User", ["avatar_url"]),
]

DEFAULT_HOSTS = "31.192.110.121"


class Command(BaseCommand):
    help = "Срезает абсолютный префикс старого хоста у медиа-ссылок в БД (→ относительные /media/...)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            action="append",
            default=None,
            help="Хост старого сервера (можно указать несколько раз). "
            "По умолчанию из env LEGACY_MEDIA_HOSTS или прежний IP.",
        )
        parser.add_argument("--apply", action="store_true", help="Записать изменения (иначе сухой прогон).")

    def handle(self, *args, **opts):
        hosts = opts.get("host") or [
            h.strip() for h in os.environ.get("LEGACY_MEDIA_HOSTS", DEFAULT_HOSTS).split(",") if h.strip()
        ]
        if not hosts:
            self.stdout.write("Не заданы хосты для нормализации — нечего делать.")
            return

        # ^https?://host(:port)?  — префикс, который срезаем.
        host_alt = "|".join(re.escape(h) for h in hosts)
        pattern = re.compile(rf"^https?://(?:{host_alt})(?::\d+)?", re.IGNORECASE)
        apply = opts["apply"]

        self.stdout.write(f"Хосты: {', '.join(hosts)}")
        self.stdout.write(f"Режим: {'ЗАПИСЬ' if apply else 'сухой прогон'}\n")

        grand_total = 0
        for app_label, model_name, fields in TARGETS:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            for field in fields:
                q = {f"{field}__iregex": rf"^https?://(?:{host_alt})"}
                qs = model.objects.filter(**q)
                changed = 0
                for obj in qs.iterator():
                    val = getattr(obj, field) or ""
                    new = pattern.sub("", val)
                    if new != val:
                        if apply:
                            setattr(obj, field, new)
                            obj.save(update_fields=[field])
                        changed += 1
                grand_total += changed
                if changed:
                    self.stdout.write(f"  {app_label}.{model_name}.{field}: {changed}")

        verb = "переписано" if apply else "будет переписано"
        self.stdout.write(self.style.SUCCESS(f"\nИтого {verb}: {grand_total}"))
        if not apply and grand_total:
            self.stdout.write("Повторите с --apply, чтобы записать.")
