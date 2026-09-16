"""MG_NOBUY: что не покупают, того в списке быть не должно.

Отчёт с прода: «из списка нужно убирать воду во всех проявлениях». Вода есть
почти в каждом рецепте — тесто, варка, бульон, — и в список она попадала
честно: позиция как позиция, с граммовкой. Только покупать её не идут, и
человек вычёркивал её каждый раз заново.

Признак стоит у товара каталога, а не списком имён в коде: что не покупается,
зависит от хозяйства. «Вода с газом» и «Вода розовая» — покупают.

Названия в тестах выдуманные: посевная миграция заводит свой каталог в каждую
тестовую базу.
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
    owner = User.objects.create_user(email="nobuy@example.com", password="pass12345", name="Owner")
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
class TestНеПокупаемое:
    def test_отмеченный_товар_в_список_не_попадает(self, menu_with_links):
        family, menu, recipe = menu_with_links
        water = Product.objects.create(name="Плюмбусная вода", skip_in_shopping=True)
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical="Плюмбусная вода", name_raw="вода", product=water, grams=500
        )

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert items == []

    def test_остальные_позиции_остаются(self, menu_with_links):
        family, menu, recipe = menu_with_links
        water = Product.objects.create(name="Плюмбусная вода", skip_in_shopping=True)
        flour = Product.objects.create(name="Плюмбусная мука")
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical="Плюмбусная вода", name_raw="вода", product=water, grams=500
        )
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical="Плюмбусная мука", name_raw="мука", product=flour, grams=300
        )

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Плюмбусная мука"}

    def test_неотмеченный_товар_не_трогаем(self, menu_with_links):
        """«Вода с газом» — покупают. Правило про признак, а не про слово в имени."""
        family, menu, recipe = menu_with_links
        soda = Product.objects.create(name="Плюмбусная вода с газом")
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical="Плюмбусная вода с газом", name_raw="вода с газом", product=soda, grams=500
        )

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Плюмбусная вода с газом"}

    def test_позиция_без_товара_остаётся(self, menu_with_links):
        """Про неё мы ничего не знаем — выбрасывать нельзя."""
        family, menu, recipe = menu_with_links
        RecipeProduct.objects.create(recipe=recipe, name_canonical="Плюмбусная роса", name_raw="роса", grams=100)

        items = build_items_from_menu(menu, family, subtract_fridge=False)

        assert _names(items) == {"Плюмбусная роса"}


@pytest.mark.django_db
class TestПравилоМиграции:
    """Миграция 0025 отмечает воду. Проверяем её правило, а не факт прогона:

    в посевном каталоге воды нет, и «тест» на готовой базе был бы зелёным,
    ничего не проверив.
    """

    def _mark(self):
        import importlib

        from django.apps import apps as global_apps

        mod = importlib.import_module("apps.fridge.migrations.0025_product_skip_in_shopping")
        mod.mark_water(global_apps, None)

    def test_вода_отмечается(self):
        water = Product.objects.create(name="Вода")

        self._mark()

        water.refresh_from_db()
        assert water.skip_in_shopping is True

    def test_воду_с_газом_не_трогаем(self):
        """Имена точные: «Вода с газом» и «Вода розовая» — покупают."""
        soda = Product.objects.create(name="Вода с газом")
        rose = Product.objects.create(name="Вода розовая")

        self._mark()

        soda.refresh_from_db()
        rose.refresh_from_db()
        assert soda.skip_in_shopping is False
        assert rose.skip_in_shopping is False

    def test_продукт_семьи_не_трогаем(self):
        """Чужая запись — чужое решение."""
        owner = User.objects.create_user(email="fam-nobuy@example.com", password="pass12345", name="Owner")
        family = Family.objects.create(name="Семья", owner=owner)
        theirs = Product.objects.create(name="Вода", owner_family=family)

        self._mark()

        theirs.refresh_from_db()
        assert theirs.skip_in_shopping is False
