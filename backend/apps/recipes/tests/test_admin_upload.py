"""MG_ADMINUPLOAD: загрузка фото рецепта из админки.

Кнопка «Загрузить файл» ходила в публичный API, а тот авторизует по JWT.
Браузер в админке шлёт только сессионную куку — на проде запрос приходил
анонимным, и пользователь видел «Upload failed: Error: 401».

Теперь загрузка идёт админской ручкой: авторизация ровно та, которой открыта
сама страница, — сессия и проверка на staff.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.users.models import User

# Минимальный валидный PNG.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def png(name="photo.png", content_type="image/png"):
    return SimpleUploadedFile(name, PNG, content_type=content_type)


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def staff_client(db):
    User.objects.create_superuser(email="adm@example.com", password="pass12345", name="Админ")
    c = Client()
    assert c.login(username="adm@example.com", password="pass12345")
    return c


def url():
    return reverse("admin:recipes_recipe_upload_media")


@pytest.mark.django_db
class TestAdminUpload:
    def test_админ_загружает_фото_сессией(self, staff_client, media_root):
        r = staff_client.post(url(), {"file": png(), "media_type": "image"})

        assert r.status_code == 200, r.content
        assert r.json()["url"].endswith(".png")

    def test_адрес_лежит_рядом_с_рецептами(self):
        """Ручка админская, а не апишная — это и было причиной 401."""
        assert url().startswith("/admin/")
        assert "/api/" not in url()

    def test_аноним_не_загружает(self, db, media_root):
        r = Client().post(url(), {"file": png(), "media_type": "image"})

        # админка уводит на страницу входа
        assert r.status_code in (302, 403)

    def test_обычный_пользователь_не_загружает(self, db, media_root):
        User.objects.create_user(email="user@example.com", password="pass12345", name="Юзер")
        c = Client()
        c.login(username="user@example.com", password="pass12345")

        r = c.post(url(), {"file": png(), "media_type": "image"})

        assert r.status_code in (302, 403)

    def test_чужой_тип_файла_отклоняется_с_объяснением(self, staff_client, media_root):
        r = staff_client.post(
            url(), {"file": png("virus.exe", "application/x-msdownload"), "media_type": "image"}
        )

        assert r.status_code == 400
        assert "JPEG" in r.json()["detail"]

    def test_без_файла_понятная_ошибка(self, staff_client, media_root):
        r = staff_client.post(url(), {"media_type": "image"})

        assert r.status_code == 400
        assert r.json()["detail"] == "Файл не передан."

    def test_get_не_принимается(self, staff_client):
        assert staff_client.get(url()).status_code == 405


@pytest.mark.django_db
class TestApiStillWorks:
    """Веб-клиент грузит фото тем же путём, что и раньше."""

    def test_api_принимает_сессию(self, staff_client, media_root):
        r = staff_client.post(
            "/api/v1/recipes/upload-media/", {"file": png(), "media_type": "image"}
        )

        assert r.status_code == 200, r.content

    def test_api_не_пускает_анонима(self, db, media_root):
        r = Client().post("/api/v1/recipes/upload-media/", {"file": png(), "media_type": "image"})

        assert r.status_code == 401


@pytest.mark.django_db
class TestWidget:
    def test_виджет_ссылается_на_админскую_ручку(self):
        from apps.recipes.forms import _MediaUploadWidget

        html = _MediaUploadWidget(media_type="image").render("image_url", "")

        assert url() in html
        assert "/api/v1/recipes/upload-media/" not in html

    def test_виджет_показывает_причину_отказа(self):
        """Раньше в статус уходил голый код состояния: «Error: 401»."""
        from apps.recipes.forms import _MediaUploadWidget

        html = _MediaUploadWidget(media_type="image").render("image_url", "")

        assert "d.detail" in html

    def test_виджет_узнаёт_протухшую_сессию(self):
        """Админка уводит на вход, ответ приходит с HTML и кодом 200 —
        без этой проверки было бы просто «не удалось»."""
        from apps.recipes.forms import _MediaUploadWidget

        html = _MediaUploadWidget(media_type="image").render("image_url", "")

        assert "r.redirected" in html
        assert "text/html" in html
        # строка проходит через gettext; в каталоге её пока нет, поэтому в
        # разметке лежит исходный текст
        assert "session expired" in html
