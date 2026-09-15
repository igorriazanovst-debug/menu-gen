"""MG_NOTENOISE: примечание рецепта не должно доходить до списка покупок.

Отчёт с прода: в списке из меню на 49 рецептов оказались «По вкусу: базилик»,
«Зелень по вкусу» и «Масло для обжарки» — в категории «Прочее». Пришли они не
из сырых ингредиентов, а из готовых связей рецепт→продукт: часть таких названий
успела осесть в общем каталоге как отдельные товары, и связь честно на них
ссылалась.

Поэтому проверка идёт именно через связи (RecipeProduct), а не через сырой
состав рецепта: путь с чисткой ИИ на лету здесь не работает вовсе.

Названия продуктов в тесте выдуманные. Посевная миграция каталога заводит в
каждую тестовую базу «Помидоры», «Яйцо куриное» и прочее, и взятое оттуда
название дало бы вторую запись в выдаче или чужой id в связи.
"""

import datetime

import pytest

from apps.family.models import Family
from apps.fridge.models import Product
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.shopping.services import build_items_from_menu
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def menu_with_links(db):
    owner = User.objects.create_user(email="noise@example.com", password="pass12345", name="Owner")
    _bootstrap_user(owner)
    family = Family.objects.get(owner=owner)

    today = datetime.date.today()
    menu = Menu.objects.create(
        family=family,
        creator_id=owner.id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )
    recipe = Recipe.objects.create(title="Тестовое блюдо", ingredients=[])
    MenuItem.objects.create(menu=menu, recipe=recipe, day_offset=0, meal_type=MenuItem.MealType.LUNCH)
    return family, menu, recipe


def _names(items):
    return {i["name"] for i in items}


@pytest.mark.django_db
class TestПримечанияВСписке:
    def test_примечание_целиком_в_список_не_попадает(self, menu_with_links):
        family, menu, recipe = menu_with_links
        RecipeProduct.objects.create(recipe=recipe, name_canonical="По вкусу", name_raw="по вкусу")
        RecipeProduct.objects.create(recipe=recipe, name_canonical="Для подачи", name_raw="для подачи")

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert items == []

    def test_продукт_с_примечанием_остаётся_продуктом(self, menu_with_links):
        family, menu, recipe = menu_with_links
        RecipeProduct.objects.create(recipe=recipe, name_canonical="Марсианка по вкусу", name_raw="марсианка")

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Марсианка"}

    def test_привязка_на_мусорную_запись_каталога_сбрасывается(self, menu_with_links):
        """«По вкусу: базилик» на проде — отдельный товар каталога с своим id.

        Очистив название, привязку надо искать заново: иначе позиция осталась
        бы висеть на мусорной записи, только под приличным именем.
        """
        family, menu, recipe = menu_with_links
        junk = Product.objects.create(name="По вкусу: криптонит", source=Product.Source.AUTO)
        RecipeProduct.objects.create(
            recipe=recipe,
            name_canonical="По вкусу: криптонит",
            name_raw="по вкусу: криптонит",
            product=junk,
        )

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Криптонит"}
        assert [i["product_id"] for i in items] == [None]

    def test_количество_из_названия_уходит_в_название_не_лезет(self, menu_with_links):
        family, menu, recipe = menu_with_links
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical="Тарелочник 2-3 ст. ложки", name_raw="тарелочник", grams=40
        )

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Тарелочник"}
        assert items[0]["quantity"] == 40

    def test_обычный_продукт_проходит_как_был(self, menu_with_links):
        """Фильтр не должен трогать то, что и так продукт."""
        family, menu, recipe = menu_with_links
        RecipeProduct.objects.create(recipe=recipe, name_canonical="Плюмбус", name_raw="плюмбус", grams=100)

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Плюмбус"}
