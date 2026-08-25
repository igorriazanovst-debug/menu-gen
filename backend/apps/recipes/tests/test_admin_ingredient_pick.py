"""MG_INGPICK: подсказки продуктов в составе рецепта.

Название ингредиента набиралось руками, и одно и то же писали по-разному
(«лук репчатый», «репчатый лук», «лук»). Связь рецепта с продуктом каталога
строится по названию, поэтому каждый новый вариант написания — это рецепт,
который не найдётся в подборе «что приготовить из холодильника».

Держаться подсказки должны на трёх вещах:

- ищут по каталогу и находят по части слова;
- НЕ отдают справочники штрих-кодов (retail, off_bulk) и догадки ИИ: это
  32 тысячи конкретных упаковок, они утопили бы один «Лук репчатый»;
- закрыты от посторонних — это админская ручка.

Отдельно проверяется, что поле состава по-прежнему принимает произвольное
название: в рецепте бывает ингредиент, которого в каталоге нет, и подсказка
не должна становиться обязательной.
"""

import json

import pytest
from django.urls import reverse

from apps.fridge.models import Product
from apps.users.models import User

URL = "/admin/recipes/recipe/ingredient-search/"


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="admin@example.com", password="pass12345", name="Админ", is_staff=True, is_superuser=True
    )


@pytest.fixture
def catalog(db):
    Product.objects.create(name="Лук репчатый", default_unit="шт", source=Product.Source.MANUAL)
    Product.objects.create(name="Лук зелёный", default_unit="пучок", source=Product.Source.MANUAL)
    Product.objects.create(name="Гречка", default_unit="г", source=Product.Source.MANUAL)
    # То, чего в подсказках быть не должно.
    Product.objects.create(name="Лук репчатый Магнит 1кг", barcode="4600000000017", source=Product.Source.RETAIL)
    Product.objects.create(name="Лукойл вода", barcode="4600000000024", source=Product.Source.OFFBULK)
    Product.objects.create(name="Лук (догадка)", barcode="4600000000031", source=Product.Source.AI)


def names(response):
    return [r["name"] for r in json.loads(response.content)["results"]]


@pytest.mark.django_db
class TestIngredientSearch:
    def test_находит_по_части_слова(self, client, staff, catalog):
        client.force_login(staff)

        r = client.get(URL, {"q": "лук"})

        assert r.status_code == 200
        assert "Лук репчатый" in names(r)

    def test_отдаёт_единицу_измерения(self, client, staff, catalog):
        """Единица подставляется в строку состава — набирать её заново незачем."""
        client.force_login(staff)

        r = client.get(URL, {"q": "гречка"})

        rows = json.loads(r.content)["results"]
        assert rows and rows[0]["unit"] == "г"

    def test_справочники_штрихкодов_в_подсказки_не_лезут(self, client, staff, catalog):
        """Иначе один «Лук репчатый» утонет в полусотне конкретных упаковок."""
        client.force_login(staff)

        found = names(client.get(URL, {"q": "лук"}))

        assert "Лук репчатый Магнит 1кг" not in found
        assert "Лукойл вода" not in found
        assert "Лук (догадка)" not in found

    def test_короткий_запрос_не_ищем(self, client, staff, catalog):
        """На одну букву подсказки бесполезны, а запрос в базу — вполне реальный."""
        client.force_login(staff)

        assert names(client.get(URL, {"q": "л"})) == []

    def test_посторонним_закрыто(self, client, catalog, db):
        """Ручка админская: каталог не тайна, но открывать её всем незачем."""
        r = client.get(URL, {"q": "лук"})

        assert r.status_code in (302, 403), r.status_code

    def test_ссылка_на_ручку_есть_в_админке(self, staff, db):
        assert reverse("admin:recipes_recipe_ingredient_search") == URL


@pytest.mark.django_db
class TestFreeTextStillWorks:
    def test_произвольное_название_принимается(self):
        """Подсказка — помощь, а не обязанность: своё название должно сохраняться."""
        from apps.recipes.forms import _IngredientsWidget

        data = {
            "ingredients_name": ["Бабушкина аджика"],
            "ingredients_quantity": ["2"],
            "ingredients_unit": ["ст. л."],
            "ingredients_grams": ["40"],
        }
        out = _IngredientsWidget().value_from_datadict(data, {}, "ingredients")

        assert out == [{"name": "Бабушкина аджика", "quantity": "2", "unit": "ст. л.", "grams": 40.0}]
