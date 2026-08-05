# MG_YOSEARCH: поиск не различает «е» и «ё».
import pytest
from django.urls import reverse

from apps.common.search import normalize_yo, yo_regex
from apps.fridge.models import Product
from apps.recipes.models import Recipe
from apps.users.models import User


def make_recipe(title: str, **kwargs) -> Recipe:
    r = Recipe(title=title, is_published=True, **kwargs)
    r._mg_skip_link_rebuild = True  # MG_RECIPELINK ходит в ИИ
    r.save()
    return r


class TestHelpers:
    def test_буквы_взаимозаменяемы(self):
        assert yo_regex("мед") == "м[её]д"
        assert yo_regex("мёд") == "м[её]д"

    def test_регистр_тоже_учтён(self):
        # поиск идёт через iregex, поэтому достаточно строчного класса
        assert yo_regex("Ёлка") == "[её]лка"

    def test_спецсимволы_экранируются(self):
        """Иначе «(» сломал бы выражение, а «.*» неожиданно расширил выдачу."""
        assert yo_regex("суп (острый)") == r"суп\ \(острый\)"
        assert ".*" not in yo_regex("а.*я")

    def test_пустой_запрос(self):
        assert yo_regex("") == ""
        assert yo_regex(None) == ""

    def test_normalize_yo(self):
        assert normalize_yo("Свёкла тёртая") == "Свекла тертая"
        assert normalize_yo(None) == ""


@pytest.mark.django_db
class TestRecipeSearch:
    @pytest.fixture
    def client(self, db):
        from rest_framework.test import APIClient

        user = User.objects.create_user(email="s@example.com", name="Ю", password="pass1234")
        c = APIClient()
        c.force_authenticate(user)
        return c

    def _titles(self, client, query):
        resp = client.get(reverse("recipe-list"), {"search": query})
        assert resp.status_code == 200
        return [r["title"] for r in resp.data["results"]]

    def test_запрос_без_ё_находит_рецепт_с_ё(self, client):
        make_recipe("Свёкла тёртая с чесноком")

        assert self._titles(client, "свекла") == ["Свёкла тёртая с чесноком"]

    def test_запрос_с_ё_находит_рецепт_без_ё(self, client):
        make_recipe("Мед с орехами")

        assert self._titles(client, "мёд") == ["Мед с орехами"]

    def test_слова_запроса_объединяются_по_и(self, client):
        make_recipe("Свёкла тёртая")
        make_recipe("Свёкла запечённая")

        assert self._titles(client, "свекла тертая") == ["Свёкла тёртая"]

    def test_обычный_поиск_не_сломан(self, client):
        make_recipe("Борщ красный")
        make_recipe("Суп грибной")

        assert self._titles(client, "борщ") == ["Борщ красный"]

    def test_чужие_рецепты_не_подмешиваются(self, client):
        make_recipe("Мёд")
        make_recipe("Молоко")

        assert self._titles(client, "мед") == ["Мёд"]

    def test_спецсимвол_в_запросе_не_роняет_поиск(self, client):
        make_recipe("Суп (острый)")

        assert self._titles(client, "(острый)") == ["Суп (острый)"]

    def test_пустой_поиск_отдаёт_всё(self, client):
        make_recipe("Мёд")
        make_recipe("Молоко")

        assert len(self._titles(client, "")) == 2


@pytest.mark.django_db
class TestProductSearch:
    @pytest.fixture
    def client(self, db):
        from rest_framework.test import APIClient

        user = User.objects.create_user(email="p@example.com", name="Ю", password="pass1234")
        c = APIClient()
        c.force_authenticate(user)
        return c

    def _names(self, client, query):
        resp = client.get(reverse("product-search"), {"q": query})
        assert resp.status_code == 200
        # выдача постраничная
        rows = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        return [p["name"] for p in rows]

    def test_продукт_с_ё_находится_без_ё(self, client):
        Product.objects.create(name="Свёкла")

        assert self._names(client, "свекла") == ["Свёкла"]

    def test_продукт_без_ё_находится_с_ё(self, client):
        Product.objects.create(name="Мед натуральный")

        assert self._names(client, "мёд") == ["Мед натуральный"]

    def test_чужой_продукт_не_попадает_в_выдачу(self, client):
        Product.objects.create(name="Мёд")
        Product.objects.create(name="Молоко")

        assert self._names(client, "мед") == ["Мёд"]


@pytest.mark.django_db
class TestAdminSearch:
    @pytest.fixture
    def admin_client(self, db):
        from django.test import Client

        User.objects.create_superuser(email="a@example.com", password="pass1234", name="Админ")
        c = Client()
        c.login(username="a@example.com", password="pass1234")
        return c

    def test_поиск_рецептов_в_админке(self, admin_client):
        make_recipe("Свёкла тёртая")
        make_recipe("Молоко")

        resp = admin_client.get("/admin/recipes/recipe/", {"q": "свекла"})

        assert resp.status_code == 200
        assert "Свёкла тёртая".encode() in resp.content
        assert "Молоко".encode() not in resp.content

    def test_поиск_продуктов_в_админке(self, admin_client):
        Product.objects.create(name="Мед")

        resp = admin_client.get("/admin/fridge/product/", {"q": "мёд"})

        assert resp.status_code == 200
        assert "Мед".encode() in resp.content
