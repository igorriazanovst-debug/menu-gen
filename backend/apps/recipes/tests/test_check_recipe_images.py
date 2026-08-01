# MG_IMGAUDIT: аудит битых картинок рецептов.
from io import StringIO

import pytest
from django.core.management import call_command

from apps.recipes.management.commands.check_recipe_images import local_path
from apps.recipes.models import Recipe


def make_recipe(**kwargs) -> Recipe:
    """Recipe без post_save-пересборки связей (MG_RECIPELINK ходит в ИИ)."""
    r = Recipe(**kwargs)
    r._mg_skip_link_rebuild = True
    r.save()
    return r


@pytest.fixture
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    images = tmp_path / "recipes" / "images"
    images.mkdir(parents=True)
    (images / "есть.png").write_bytes(b"\x89PNG")
    return tmp_path


class TestLocalPath:
    def test_срезает_префикс_media(self, media):
        assert local_path("/media/recipes/images/есть.png") == media / "recipes" / "images" / "есть.png"

    def test_внешняя_ссылка_не_путь(self, media):
        assert local_path("https://example.com/a.png") is None
        assert local_path("http://31.192.110.121:8003/media/a.png") is None

    def test_пустая_ссылка(self, media):
        assert local_path("") is None

    def test_разэкранирует_проценты(self, media):
        # Кириллица в имени файла приезжает из БД в percent-encoding.
        assert local_path("/media/recipes/images/%D0%B5%D1%81%D1%82%D1%8C.png").name == "есть.png"


@pytest.mark.django_db
class TestCommand:
    def test_целая_картинка_не_попадает_в_отчёт(self, media):
        make_recipe(title="Целая", image_url="/media/recipes/images/есть.png")

        out = StringIO()
        call_command("check_recipe_images", stdout=out)
        result = out.getvalue()

        assert "Картинка на месте:         1" in result
        assert "Битых картинок не найдено." in result

    def test_находит_отсутствующий_файл(self, media):
        make_recipe(title="Паста с сардинами", image_url="/media/recipes/images/нет.png")

        out = StringIO()
        call_command("check_recipe_images", stdout=out)
        result = out.getvalue()

        assert "Файл не найден на диске:   1" in result
        assert "Паста с сардинами" in result

    def test_отделяет_внешние_ссылки(self, media):
        make_recipe(title="Внешняя", image_url="http://31.192.110.121:8003/media/x.png")

        out = StringIO()
        call_command("check_recipe_images", stdout=out)
        result = out.getvalue()

        assert "Ссылка на внешний хост:    1" in result
        assert "--check-remote" in result

    def test_считает_рецепты_без_картинки(self, media):
        make_recipe(title="Без картинки", image_url=None)
        make_recipe(title="Пустая строка", image_url="   ")

        out = StringIO()
        call_command("check_recipe_images", stdout=out)

        assert "Картинки нет вовсе:        2" in out.getvalue()

    def test_опрос_внешних_ссылок(self, media, monkeypatch):
        make_recipe(title="Мертвая ссылка", image_url="https://example.com/gone.png")

        class _Resp:
            status_code = 404

        monkeypatch.setattr("requests.head", lambda *a, **k: _Resp())
        monkeypatch.setattr("requests.get", lambda *a, **k: _Resp())

        out = StringIO()
        call_command("check_recipe_images", "--check-remote", stdout=out)
        result = out.getvalue()

        assert "[404]" in result
        assert "Недоступных внешних: 1 из 1" in result

    def test_сетевая_ошибка_не_роняет_команду(self, media, monkeypatch):
        make_recipe(title="Нет сети", image_url="https://example.com/x.png")

        def _boom(*a, **k):
            raise ConnectionError("нет сети")

        monkeypatch.setattr("requests.head", _boom)

        out = StringIO()
        call_command("check_recipe_images", "--check-remote", stdout=out)

        assert "ConnectionError" in out.getvalue()
