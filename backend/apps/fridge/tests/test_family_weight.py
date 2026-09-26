"""MG_FAMWEIGHT: вес семьи перекрывает общий.

Общий каталог врал бы половине людей. «Творог 5%» — обобщённая запись, к
которой привязаны рецепты, а пачки у всех разные: поставив ей 200 г, мы делаем
верно тем, кто берёт по 200, и вдвое неверно тем, кто берёт по 400. Причём
молча — вес никто не открывает, все смотрят на список покупок.

Проверяется и обратное, менее очевидное: чужой вес не должен просачиваться. Две
семьи, у каждой своя пачка, и ни одна не видит чужую цифру.

Названия выдуманы: посевная миграция заводит каталог в каждую тестовую базу.
"""

import datetime
from decimal import Decimal

import pytest

from apps.family.models import Family
from apps.fridge.models import FridgeItem, Product, ProductUnitWeight
from apps.fridge.units import to_grams, unit_weight_index
from apps.fridge.writeoff import write_off_menu_item
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.shopping.services import build_items_from_menu
from apps.users.models import User
from apps.users.views import _bootstrap_user


def _family(email):
    user = User.objects.create_user(email=email, password="pass12345", name="Хозяин")
    _bootstrap_user(user)
    return Family.objects.get(owner=user)


@pytest.fixture
def curd(db):
    """Обобщённая запись каталога: пачки у всех разные."""
    return Product.objects.create(name="Творог плюмбусный")


@pytest.fixture
def ours(db):
    return _family("famweight-ours@example.com")


@pytest.fixture
def theirs(db):
    return _family("famweight-theirs@example.com")


def _dish(family, product, grams):
    today = datetime.date.today()
    menu = Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )
    recipe = Recipe.objects.create(title="Блюдо с творогом", ingredients=[])
    RecipeProduct.objects.create(
        recipe=recipe, name_canonical=product.name, name_raw=product.name.lower(), product=product, grams=grams
    )
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        day_offset=0,
        meal_type=MenuItem.MealType.LUNCH,
        meal_slot="lunch",
    )


@pytest.mark.django_db
class TestДваУровня:
    def test_общий_вес_работает_без_семейного(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))

        index = unit_weight_index([curd.id], family=ours)

        assert index[(curd.id, "упаковка")] == Decimal("200.00")

    def test_семейный_перекрывает_общий(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=ours)

        index = unit_weight_index([curd.id], family=ours)

        assert index[(curd.id, "упаковка")] == Decimal("400.00")

    def test_чужой_вес_не_виден(self, curd, ours, theirs):
        """У соседей пачка вдвое больше — на наш холодильник это не влияет."""
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=theirs)

        index = unit_weight_index([curd.id], family=ours)

        assert index[(curd.id, "упаковка")] == Decimal("200.00")

    def test_без_семьи_только_общие(self, curd, ours):
        """Запрос без семьи не должен подхватить чью-то личную цифру."""
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=ours)

        assert unit_weight_index([curd.id]) == {}
        assert to_grams(Decimal("1"), "упаковка", curd.id) is None

    def test_семейный_без_общего_тоже_работает(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("350"), family=ours)

        assert to_grams(Decimal("2"), "упаковка", curd.id, family=ours) == Decimal("700")

    def test_две_семьи_могут_задать_своё(self, curd, ours, theirs):
        """Ограничение уникальности не должно мешать соседям.

        Одна общая строка на товар и по одной на каждую семью — это разные
        ограничения, и в Postgres они разведены условиями.
        """
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=ours)
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("180"), family=theirs)

        assert unit_weight_index([curd.id], family=ours)[(curd.id, "упаковка")] == Decimal("400.00")
        assert unit_weight_index([curd.id], family=theirs)[(curd.id, "упаковка")] == Decimal("180.00")
        assert unit_weight_index([curd.id])[(curd.id, "упаковка")] == Decimal("200.00")


@pytest.mark.django_db
class TestСписаниеПоСвоемуВесу:
    def test_списывается_по_весу_своей_семьи(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=ours)
        item = FridgeItem.objects.create(
            family=ours, product=curd, name=curd.name, quantity=Decimal("2"), unit="упаковка"
        )
        dish = _dish(ours, curd, 400)

        write_off_menu_item(dish)

        item.refresh_from_db()
        # Пачка своя, на 400 г — блюду хватило одной.
        assert item.quantity == Decimal("1.00")

    def test_без_своего_веса_берётся_общий(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        item = FridgeItem.objects.create(
            family=ours, product=curd, name=curd.name, quantity=Decimal("2"), unit="упаковка"
        )
        dish = _dish(ours, curd, 400)

        write_off_menu_item(dish)

        item.refresh_from_db()
        # Пачки по 200 г — ушли обе.
        assert item.quantity == Decimal("0.00")


@pytest.mark.django_db
class TestСписокПокупокПоСвоемуВесу:
    def test_свой_вес_закрывает_потребность(self, curd, ours):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=ours)
        FridgeItem.objects.create(family=ours, product=curd, name=curd.name, quantity=Decimal("1"), unit="упаковка")
        dish = _dish(ours, curd, 400)

        rows = build_items_from_menu(dish.menu, ours, subtract_fridge=True)

        assert curd.name not in {r["name"] for r in rows}

    def test_общий_вес_потребность_не_закрывает(self, curd, ours):
        """Та же пачка по общему весу — 200 г, и половины не хватает."""
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        FridgeItem.objects.create(family=ours, product=curd, name=curd.name, quantity=Decimal("1"), unit="упаковка")
        dish = _dish(ours, curd, 400)

        rows = build_items_from_menu(dish.menu, ours, subtract_fridge=True)

        row = next(r for r in rows if r["name"] == curd.name)
        assert row["quantity"] == Decimal("200")
