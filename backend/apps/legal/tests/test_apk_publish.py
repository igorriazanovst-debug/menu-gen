"""MG_APKSITE: подписанная сборка, выложенная на сайте.

Модерация в RuStore идёт долго, а исправление иногда нужно людям сегодня.
Файл тот же самый, что уходит в магазин: пересобранный с другим ключом Android
не поставит поверх уже установленного, и человек останется со старой версией и
непонятной ошибкой.
"""

import io
import zipfile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.legal.models import AndroidBuild


def make_apk(path, signed=True):
    """Минимальный файл, похожий на apk: zip с манифестом (и подписью v1)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AndroidManifest.xml", "binary-ish")
        z.writestr("classes.dex", "code")
        if signed:
            z.writestr("META-INF/CERT.RSA", "signature")
    path.write_bytes(buf.getvalue())
    return path


@pytest.fixture
def apk(tmp_path):
    return make_apk(tmp_path / "menugen-release-3-abc1234.apk")


@pytest.mark.django_db
class TestPublish:
    def test_сборка_выкладывается_с_размером_и_суммой(self, apk, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path / "media"

        call_command("publish_apk", str(apk), version_name="1.0.2")

        build = AndroidBuild.objects.get()
        assert build.version_name == "1.0.2"
        assert build.size_bytes == apk.stat().st_size
        assert len(build.sha256) == 64
        assert build.is_published is True

    def test_файл_копируется_в_media(self, apk, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path / "media"

        call_command("publish_apk", str(apk), version_name="1.0.2")

        assert (tmp_path / "media" / "apk" / "menugen-1.0.2.apk").exists()

    def test_новая_сборка_снимает_с_сайта_прежнюю(self, apk, settings, tmp_path):
        """На странице должна быть одна ссылка, а не список версий."""
        settings.MEDIA_ROOT = tmp_path / "media"
        call_command("publish_apk", str(apk), version_name="1.0.2")

        call_command("publish_apk", str(apk), version_name="1.0.3")

        assert AndroidBuild.objects.filter(is_published=True).count() == 1
        assert AndroidBuild.current().version_name == "1.0.3"

    def test_прежняя_запись_не_удаляется(self, apk, settings, tmp_path):
        """У кого-то может быть открыта старая ссылка — пусть отдаёт файл."""
        settings.MEDIA_ROOT = tmp_path / "media"
        call_command("publish_apk", str(apk), version_name="1.0.2")

        call_command("publish_apk", str(apk), version_name="1.0.3")

        assert AndroidBuild.objects.count() == 2

    def test_не_apk_отвергается(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path / "media"
        junk = tmp_path / "readme.txt"
        junk.write_text("не архив вовсе")

        with pytest.raises(CommandError):
            call_command("publish_apk", str(junk), version_name="1.0.2")

    def test_zip_без_манифеста_тоже_отвергается(self, tmp_path, settings):
        """Иначе выложили бы zip с исходниками и заметили бы это по жалобам."""
        settings.MEDIA_ROOT = tmp_path / "media"
        path = tmp_path / "sources.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("main.dart", "void main() {}")
        path.write_bytes(buf.getvalue())

        with pytest.raises(CommandError):
            call_command("publish_apk", str(path), version_name="1.0.2")

    def test_unpublish_убирает_ссылку_с_сайта(self, apk, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path / "media"
        call_command("publish_apk", str(apk), version_name="1.0.2")

        call_command("publish_apk", str(apk), version_name="1.0.2", unpublish=True)

        assert AndroidBuild.current() is None


@pytest.mark.django_db
class TestPublicApi:
    def test_ссылка_отдаётся_без_входа(self, apk, settings, tmp_path):
        """Человек приходит на сайт именно за тем, чтобы поставить приложение."""
        settings.MEDIA_ROOT = tmp_path / "media"
        call_command("publish_apk", str(apk), version_name="1.0.2", notes="Починили вход через Telegram")

        r = APIClient().get(reverse("android-build"))

        assert r.status_code == 200
        build = r.data["build"]
        assert build["version_name"] == "1.0.2"
        assert build["url"].endswith("/media/apk/menugen-1.0.2.apk")
        assert build["notes"] == "Починили вход через Telegram"

    def test_пока_нечего_выкладывать_сайт_молчит(self, db):
        """Пустой ответ, а не битая ссылка на несуществующий файл."""
        r = APIClient().get(reverse("android-build"))

        assert r.status_code == 200
        assert r.data["build"] is None
