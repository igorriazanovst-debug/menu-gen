"""MG_MORPHSEARCH: поиск находит слово в любой форме.

«Тушеная» должна находить «тушенное», «яйца» — «яйцо», «супы» — «суп».
Отдельно закреплено, чего стеммер НЕ умеет (менять корень) — чтобы правка
корня не выглядела потом поломкой.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.common.morphology import ru_stem, stem_prefix
from apps.common.search import search_regex
from apps.fridge.models import Product
from apps.recipes.models import Recipe
from apps.users.models import User


def make_recipe(title: str, **kwargs) -> Recipe:
    r = Recipe(title=title, is_published=True, **kwargs)
    r._mg_skip_link_rebuild = True  # MG_RECIPELINK ходит в ИИ
    r.save()
    return r


class TestStem:
    @pytest.mark.parametrize(
        "forms",
        [
            ("тушеная", "тушенная", "тушёное", "тушеный"),
            ("жареный", "жаренная", "жареные"),
            ("запеченный", "запечённые", "запеченная"),
            ("суп", "супы", "супом", "супов"),
            ("яйцо", "яйца", "яйцами"),
            ("котлета", "котлеты", "котлетами"),
            ("овощ", "овощи", "овощами"),
            ("пельмень", "пельмени", "пельменями"),
        ],
    )
    def test_формы_одного_слова_дают_одну_основу(self, forms):
        stems = {ru_stem(f) for f in forms}

        assert len(stems) == 1, f"{forms} → {stems}"

    def test_основа_всегда_начало_слова(self):
        """На этом держится поиск подстрокой: основа обязана быть префиксом."""
        for word in ["тушенная", "запечённые", "картофельный", "вареники", "молоко"]:
            assert word.replace("ё", "е").startswith(ru_stem(word))

    def test_короткие_слова_не_обрезаются(self):
        """«Уха» → «ух» искало бы «ухо», «ухват» и что попало."""
        for word in ["суп", "рис", "чай", "уха", "еда"]:
            assert ru_stem(word) == word

    def test_основа_не_короче_трёх_букв(self):
        assert len(ru_stem("яйца")) >= 3

    def test_латиница_и_цифры_не_трогаются(self):
        assert ru_stem("pizza") == "pizza"
        assert stem_prefix("2024") == "2024"

    def test_смены_корня_не_ждём(self):
        """Ограничение стеммера без словаря: «курица» и «куриный» — разное."""
        assert ru_stem("курица") != ru_stem("куриный")

    def test_регулярное_выражение_из_основы(self):
        # окончание отброшено, «е» осталась взаимозаменяемой с «ё»
        assert search_regex("тушеная") == "туш[её]н"
        assert search_regex("тушёная") == "туш[её]н"


@pytest.fixture
def client(db):
    from rest_framework.test import APIClient

    user = User.objects.create_user(email="forms@example.com", name="Ю", password="pass1234")
    c = APIClient()
    c.force_authenticate(user)
    return c


def titles(client, query):
    resp = client.get(reverse("recipe-list"), {"search": query})
    assert resp.status_code == 200
    return sorted(r["title"] for r in resp.data["results"])


@pytest.mark.django_db
class TestRecipeSearchForms:
    def test_тушеная_находит_тушенную(self, client):
        make_recipe("Капуста тушенная с мясом")

        assert titles(client, "тушеная") == ["Капуста тушенная с мясом"]

    def test_и_наоборот(self, client):
        make_recipe("Тушеная капуста")

        assert titles(client, "тушенная") == ["Тушеная капуста"]

    def test_форма_с_ё_тоже(self, client):
        make_recipe("Картошка тушёная")

        assert titles(client, "тушенная") == ["Картошка тушёная"]

    def test_множественное_число_находит_единственное(self, client):
        make_recipe("Суп гороховый")

        assert titles(client, "супы") == ["Суп гороховый"]

    def test_единственное_находит_множественное(self, client):
        make_recipe("Сырники из творога")

        assert titles(client, "сырник") == ["Сырники из творога"]

    def test_другое_слово_не_подмешивается(self, client):
        make_recipe("Капуста тушенная")
        make_recipe("Курица жареная")

        assert titles(client, "тушеная") == ["Капуста тушенная"]

    def test_несколько_слов_по_прежнему_по_и(self, client):
        make_recipe("Капуста тушенная с мясом")
        make_recipe("Картошка тушёная")

        assert titles(client, "тушеная капуста") == ["Капуста тушенная с мясом"]

    def test_поиск_по_части_слова_не_сломан(self, client):
        make_recipe("Борщ красный")

        assert titles(client, "борщ") == ["Борщ красный"]


@pytest.mark.django_db
class TestProductSearchForms:
    def test_продукт_находится_в_другой_форме(self, client):
        # Засев каталога держит «Яйца куриные», и запрос «яйца» находил обе
        # записи. Проверяем здесь поиск по другой грамматической форме, а не
        # содержимое справочника, — поэтому посевные совпадения убираем.
        Product.objects.filter(name__icontains="яйц").delete()
        Product.objects.create(name="Яйцо куриное")

        resp = client.get(reverse("product-search"), {"q": "яйца"})

        assert resp.status_code == 200
        rows = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        assert [p["name"] for p in rows] == ["Яйцо куриное"]


@pytest.mark.django_db
class TestAdminSearchForms:
    def test_админка_тоже_знает_формы(self, db):
        from django.test import Client

        User.objects.create_superuser(email="adm@example.com", password="pass1234", name="Админ")
        c = Client()
        c.login(username="adm@example.com", password="pass1234")
        make_recipe("Капуста тушенная")
        make_recipe("Молоко")

        resp = c.get("/admin/recipes/recipe/", {"q": "тушеная"})

        assert resp.status_code == 200
        assert "Капуста тушенная".encode() in resp.content
        assert "Молоко".encode() not in resp.content


@pytest.mark.django_db
class TestSearchProbeCommand:
    """Команда нужна, чтобы проверить выражение на живой базе (Postgres),
    а тесты идут на SQLite — поэтому она сама должна работать наверняка."""

    def test_показывает_основу_и_находки(self, capsys):
        make_recipe("Капуста тушенная")
        make_recipe("Молоко")

        call_command("search_probe", "тушеная")

        out = capsys.readouterr().out
        assert "основа «тушен»" in out
        assert "Капуста тушенная" in out
        assert "Молоко" not in out

    def test_умеет_продукты(self, capsys):
        Product.objects.create(name="Яйцо куриное")

        call_command("search_probe", "--model", "product", "яйца")

        assert "Яйцо куриное" in capsys.readouterr().out
