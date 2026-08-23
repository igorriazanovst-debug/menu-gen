"""MG_APKSITE: выложить подписанную сборку приложения на сайт.

Модерация в RuStore идёт долго, а исправление иногда нужно людям сегодня.
Команда кладёт файл в media и заводит запись, которую сайт показывает на
странице входа.

Загрузка идёт файлом на сервере, а не через админку: apk весит десятки
мегабайт и упёрся бы в ограничение nginx на размер тела запроса — а поднимать
его ради одной формы значит открывать этот размер всем остальным ручкам.

Путь берётся ВНУТРИ контейнера: команда выполняется там, а каталоги хоста
(backups, домашний каталог) в него не смонтированы — видны только backend/ и
том с media. Поэтому файл сначала кладут в контейнер:

    cd /opt/menugen
    docker compose cp ./backups/menugen-release-3-abc1234.apk backend:/tmp/menugen.apk
    docker compose exec -T backend python manage.py publish_apk /tmp/menugen.apk \\
        --version-name 1.0.2 --version-code 3

    # снять выложенное с сайта:  --unpublish
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.legal.models import AndroidBuild

# Подпись v1 лежит в META-INF (.RSA/.DSA/.EC). Схемы v2/v3 живут в блоке
# подписи самого zip и в архиве не видны, поэтому отсутствие этих файлов —
# повод предупредить, а не отказать.
V1_SIGNATURE_SUFFIXES = (".rsa", ".dsa", ".ec")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_apk(path: Path) -> bool:
    """apk — это zip с AndroidManifest.xml внутри."""
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as z:
        return "AndroidManifest.xml" in z.namelist()


def has_v1_signature(path: Path) -> bool:
    with zipfile.ZipFile(path) as z:
        return any(
            n.upper().startswith("META-INF/") and n.lower().endswith(V1_SIGNATURE_SUFFIXES) for n in z.namelist()
        )


class Command(BaseCommand):
    help = "Выложить подписанный apk на сайт (страница входа)."

    def add_arguments(self, parser):
        # Ничего не помечено required: со снятием сборки с сайта (--unpublish)
        # ни файл, ни версия не нужны, и требовать их было бы издевательством.
        # Проверяем ниже, по делу.
        parser.add_argument("path", nargs="?", help="Путь к apk на сервере")
        # Не --version: так называется встроенный ключ Django, и argparse
        # отказывается регистрировать команду целиком.
        parser.add_argument("--version-name", help="Версия для показа: 1.0.2")
        parser.add_argument("--version-code", type=int, help="versionCode сборки (номер прогона CI)")
        parser.add_argument("--notes", default="", help="Что нового (показывается рядом со ссылкой)")
        parser.add_argument(
            "--unpublish", action="store_true", help="Снять с сайта всё выложенное и ничего не выкладывать"
        )

    def handle(self, *args, **opts):
        if opts["unpublish"]:
            count = AndroidBuild.objects.filter(is_published=True).update(is_published=False)
            self.stdout.write(self.style.SUCCESS(f"Снято с сайта сборок: {count}"))
            return

        if not opts["path"] or not opts["version_name"]:
            raise CommandError("Нужны путь к apk и --version-name")
        # Номер сборки обязателен: приложение сравнивает именно его, а не
        # название версии. Без него апдейтер молча ничего не предложит — и
        # понять, почему обновление «не приходит», будет неоткуда.
        if opts["version_code"] is None:
            raise CommandError("Нужен --version-code: по нему приложение понимает, что версия новее")

        src = Path(opts["path"]).expanduser()
        if not src.exists():
            raise CommandError(f"Файл не найден: {src}")
        if not looks_like_apk(src):
            raise CommandError(f"Это не apk (нет AndroidManifest.xml внутри): {src}")
        if not has_v1_signature(src):
            self.stdout.write(
                self.style.WARNING(
                    "  Подписи v1 в архиве нет. Для сборок с v2/v3 это нормально, "
                    "но если файл собран без ключа — его нельзя ставить поверх магазинного."
                )
            )

        version = str(opts["version_name"]).strip()
        dest_dir = Path(settings.MEDIA_ROOT) / "apk"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"menugen-{version}.apk"
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)

        # Прежние сборки не удаляем: у кого-то может быть открыта старая ссылка,
        # и пусть она лучше отдаёт файл, чем 404. Со страницы уходит только
        # отметка «показывать».
        AndroidBuild.objects.filter(is_published=True).update(is_published=False)

        build = AndroidBuild.objects.create(
            version_name=version,
            version_code=opts["version_code"],
            file=f"apk/{dest.name}",
            size_bytes=dest.stat().st_size,
            sha256=sha256_of(dest),
            notes=opts["notes"] or "",
            is_published=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Выложено: {build.version_name}, {build.size_bytes / (1024 * 1024):.1f} МБ\n"
                f"  файл:   {settings.MEDIA_URL}apk/{dest.name}\n"
                f"  SHA-256: {build.sha256}"
            )
        )
