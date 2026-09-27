"""MG_SAY7PUB: публикация рецептов say7 с появившейся обложкой.

Главное, что здесь проверяется, — что команда смотрит на файл, а не на строку
в поле. Ссылка на несуществующий файл выглядит в админке как настоящая, и
опубликованный по ней рецепт вернёт пустую карточку — ровно то, ради чего
импорт держит say7 неопубликованным.

Названия выдуманы: посевная миграция заводит каталог продуктов в каждую
тестовую базу, и совпадение с ним читалось бы как поломка выборки.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.recipes.models import Recipe


def _recipe(title, *, legacy="say7:1", dish_type="main", image_url="", published=False):
    return Recipe.objects.create(
        title=title,
        legacy_id=legacy,
        dish_type=dish_type,
        image_url=image_url,
        is_published=published,
        ingredients=[],
    )


@pytest.fixture
def cover(tmp_path, settings):
    """Настоящий файл обложки в MEDIA_ROOT."""
    settings.MEDIA_ROOT = str(tmp_path)
    settings.MEDIA_URL = "/media/"
    folder = tmp_path / "recipes"
    folder.mkdir()
    (folder / "plumbus.jpg").write_bytes(b"jpeg")
    return "/media/recipes/plumbus.jpg"


def run(*args):
    out = StringIO()
    call_command("mg_publish_say7", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestКогоПубликуем:
    def test_обложка_на_диске_публикуется(self, cover):
        recipe = _recipe("Плюмбус тушёный", image_url=cover)

        run("--apply")

        recipe.refresh_from_db()
        assert recipe.is_published is True

    def test_без_обложки_остаётся_неопубликованным(self, cover):
        recipe = _recipe("Плюмбус без картинки", legacy="say7:2")

        run("--apply")

        recipe.refresh_from_db()
        assert recipe.is_published is False

    def test_ссылка_без_файла_не_публикуется(self, cover):
        """Строка в поле есть, файла нет — это и есть пустая карточка."""
        recipe = _recipe("Плюмбус с битой ссылкой", legacy="say7:3", image_url="/media/recipes/нет-такого.jpg")

        run("--apply")

        recipe.refresh_from_db()
        assert recipe.is_published is False

    def test_абсолютная_ссылка_на_свой_хост_это_обложка(self, cover, settings):
        """Админка пишет обложку абсолютной ссылкой на наш же домен.

        Именно на этом команда и ошиблась в первый раз: тридцать готовых
        обложек она сочла «ссылками на чужой хост» и не опубликовала ни одной.
        """
        settings.ALLOWED_HOSTS = ["menugen.ru"]
        recipe = _recipe(
            "Плюмбус с абсолютной ссылкой",
            legacy="say7:11",
            image_url="https://menugen.ru/media/recipes/plumbus.jpg",
        )

        run("--apply")

        recipe.refresh_from_db()
        assert recipe.is_published is True

    def test_чужая_ссылка_только_по_явному_разрешению(self, cover):
        recipe = _recipe("Плюмбус с чужой картинкой", legacy="say7:4", image_url="https://example.com/p.jpg")

        run("--apply")
        recipe.refresh_from_db()
        assert recipe.is_published is False

        run("--allow-external", "--apply")
        recipe.refresh_from_db()
        assert recipe.is_published is True


@pytest.mark.django_db
class TestЧегоНеТрогаем:
    def test_салаты_не_публикуются(self, cover):
        salad = _recipe("Салат плюмбусный", legacy="say7:5", dish_type="salad", image_url=cover)

        run("--apply")

        salad.refresh_from_db()
        assert salad.is_published is False

    def test_салат_публикуется_если_назвать_его_явно(self, cover):
        salad = _recipe("Салат плюмбусный", legacy="say7:6", dish_type="salad", image_url=cover)

        run("--dish-type", "salad", "--apply")

        salad.refresh_from_db()
        assert salad.is_published is True

    def test_чужой_источник_не_трогается(self, cover):
        """Своими считаем только записи с нашим legacy_id."""
        alien = _recipe("Второе не из say7", legacy="menunedeli:1", image_url=cover)

        run("--apply")

        alien.refresh_from_db()
        assert alien.is_published is False

    def test_уже_опубликованный_не_ломается(self, cover):
        live = _recipe("Плюмбус давно в выдаче", legacy="say7:7", image_url=cover, published=True)

        run("--apply")

        live.refresh_from_db()
        assert live.is_published is True


@pytest.mark.django_db
class TestПредпросмотр:
    def test_без_apply_ничего_не_меняется(self, cover):
        recipe = _recipe("Плюмбус на предпросмотре", image_url=cover)

        out = run()

        recipe.refresh_from_db()
        assert recipe.is_published is False
        assert "--apply" in out

    def test_список_печатается_целиком(self, cover):
        """Пропущенных показываем поимённо: часть из них чинится за минуту."""
        _recipe("Плюмбус с обложкой", legacy="say7:8", image_url=cover)
        _recipe("Плюмбус без обложки", legacy="say7:9")

        out = run()

        assert "Плюмбус с обложкой" in out
        assert "Плюмбус без обложки" in out
        assert "обложки нет" in out

    def test_сообщает_сколько_салатов_ждёт(self, cover):
        _recipe("Салат плюмбусный", legacy="say7:10", dish_type="salad", image_url=cover)

        out = run()

        assert "Салатов ждёт публикации: 1" in out
