# MG_IMGAUDIT: аудит битых картинок рецептов.
from io import StringIO

import pytest
from django.core.management import call_command

from apps.recipes.management.commands.check_recipe_images import join_steps, local_path
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

    def test_экспорт_списка_без_фото(self, media, tmp_path):
        make_recipe(
            title="Омлет-рулет",
            image_url=None,
            dish_type="breakfast_dish",
            country="Россия",
            steps=[{"text": "Взбить яйца"}, "Свернуть рулетом"],
        )
        make_recipe(title="С фото", image_url="/media/recipes/images/есть.png")

        csv_path = tmp_path / "no_photo.csv"
        call_command("check_recipe_images", "--export-empty", str(csv_path), stdout=StringIO())
        content = csv_path.read_text(encoding="utf-8-sig")

        assert "Омлет-рулет" in content
        assert "С фото" not in content
        assert "breakfast_dish" in content
        # ссылка на карточку в админке — чтобы сразу открыть и загрузить фото
        assert "/admin/recipes/recipe/" in content
        assert content.splitlines()[0].startswith("id;")
        assert content.rstrip().endswith("1) Взбить яйца 2) Свернуть рулетом")


class TestJoinSteps:
    def test_нумерует_шаги(self):
        assert join_steps(["Нарезать", "Посолить"]) == "1) Нарезать 2) Посолить"

    def test_понимает_объекты_с_текстом(self):
        # формат шага зависит от того, каким импортом приехал рецепт
        assert join_steps([{"text": "Взбить", "photo": "x.png"}]) == "1) Взбить"

    def test_схлопывает_переводы_строк(self):
        assert join_steps(["Первая\nвторая  строка"]) == "1) Первая вторая строка"

    def test_пропускает_пустые(self):
        assert join_steps(["", None, {"text": "  "}, "Готово"]) == "1) Готово"

    def test_нет_шагов(self):
        assert join_steps(None) == ""
        assert join_steps([]) == ""
