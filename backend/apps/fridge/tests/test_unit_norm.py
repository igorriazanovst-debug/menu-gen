"""MG_UNITNORM: штуки, упаковки и литры сводятся с граммами рецепта.

Это чинит T-36. На проде было так: блюду нужны «Яйца куриные 50 г», в
холодильнике лежат «яйца 30 шт», товар определяется верно (#41, синоним
отрабатывает) — и всё равно строка уходит в «не хватило». Размерности разные,
перевести было нечем.

Проверяется оба конца сразу, потому что перевод у них общий: списание при
«приготовил» и вычитание холодильника при сборке списка покупок. Если правило
разойдётся, список покупок разойдётся с холодильником молча — оба места просто
не находят совпадения и ничего об этом не говорят.

Отдельно закреплено то, чего делать НЕЛЬЗЯ: без записи о весе никакого
перевода не происходит. Выдуманный вес не виден никому, а уносит из
холодильника не то количество.

Названия выдуманы: посевная миграция заводит каталог в каждую тестовую базу.
"""

import datetime
from decimal import Decimal

import pytest

from apps.family.models import Family
from apps.fridge.models import FridgeItem, Product, ProductUnitWeight
from apps.fridge.units import from_grams, grams_per_unit, to_grams, unit_weight_index
from apps.fridge.writeoff import write_off_menu_item
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.shopping.services import build_items_from_menu
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner(db):
    user = User.objects.create_user(email="units@example.com", password="pass12345", name="Хозяин")
    _bootstrap_user(user)
    return user


@pytest.fixture
def family(owner):
    return Family.objects.get(owner=owner)


@pytest.fixture
def egg(db):
    """Яйцо плюмбусиное: лежит штуками, в рецептах — граммами."""
    return Product.objects.create(name="Яйцо плюмбусиное")


@pytest.fixture
def menu(family, owner):
    today = datetime.date.today()
    return Menu.objects.create(
        family=family,
        creator_id=owner.id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )


def _dish(menu, links, title="Блюдо"):
    recipe = Recipe.objects.create(title=title, ingredients=[])
    for product, grams in links:
        RecipeProduct.objects.create(
            recipe=recipe,
            name_canonical=product.name,
            name_raw=product.name.lower(),
            product=product,
            grams=grams,
        )
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        day_offset=0,
        meal_type=MenuItem.MealType.LUNCH,
        meal_slot="lunch",
    )


@pytest.mark.django_db
class TestПеревод:
    def test_штуки_переводятся_в_граммы(self, egg):
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("55"))

        assert to_grams(Decimal("3"), "шт", egg.id) == Decimal("165")

    def test_граммы_и_килограммы_считаются_без_справочника(self, egg):
        """Это арифметика, а не свойство товара — справочник тут ни при чём."""
        assert to_grams(Decimal("2"), "кг", egg.id) == Decimal("2000")
        assert to_grams(Decimal("250"), "г", None) == Decimal("250")

    def test_без_записи_перевода_нет(self, egg):
        assert to_grams(Decimal("3"), "шт", egg.id) is None
        assert grams_per_unit(egg.id, "упаковка") is None

    def test_написание_единицы_не_мешает(self, egg):
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("55"))

        assert to_grams(Decimal("2"), "шт.", egg.id) == Decimal("110")
        assert to_grams(Decimal("2"), "штук", egg.id) == Decimal("110")

    def test_обратный_перевод(self, egg):
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))

        assert from_grams(Decimal("150"), "шт", egg.id) == Decimal("3")

    def test_вес_чужого_товара_не_применяется(self, egg):
        other = Product.objects.create(name="Гурда плюмбусиная")
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("55"))

        assert to_grams(Decimal("3"), "шт", other.id) is None

    def test_индекс_берёт_только_запрошенное(self, egg):
        other = Product.objects.create(name="Гурда плюмбусиная")
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("55"))
        ProductUnitWeight.objects.create(product=other, unit="шт", grams=Decimal("70"))

        index = unit_weight_index([egg.id])

        assert index == {(egg.id, "шт"): Decimal("55.00")}


@pytest.mark.django_db
class TestСписаниеЧерезПеревод:
    def test_штуки_в_холодильнике_закрывают_граммы_рецепта(self, family, menu, egg):
        """Тот самый случай с прода: 30 шт в холодильнике, 50 г в рецепте."""
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))
        item = FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("30"), unit="шт")
        dish = _dish(menu, [(egg, 100)])

        write_off, _ = write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("28.00")  # ушло два яйца
        assert write_off.lines.filter(shortfall__isnull=False).count() == 0

    def test_списанное_пишется_в_единице_позиции(self, family, menu, egg):
        """Отмена должна вернуть штуки, а не граммы, — иначе вернёт не то."""
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))
        FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("30"), unit="шт")
        dish = _dish(menu, [(egg, 100)])

        write_off, _ = write_off_menu_item(dish)

        line = write_off.lines.get()
        assert line.quantity == Decimal("2")
        assert line.unit == "шт"

    def test_нехватка_считается_после_перевода(self, family, menu, egg):
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))
        FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("1"), unit="шт")
        dish = _dish(menu, [(egg, 150)])

        write_off, _ = write_off_menu_item(dish)

        short = write_off.lines.get(shortfall__isnull=False)
        assert short.shortfall == Decimal("100.00")  # одно яйцо нашлось, ста граммов нет
        assert short.shortfall_unit == "г"

    def test_без_веса_всё_как_раньше(self, family, menu, egg):
        """Ничего не выдумываем: нет записи — нет перевода, честная нехватка."""
        item = FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("30"), unit="шт")
        dish = _dish(menu, [(egg, 100)])

        write_off, _ = write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("30.00")
        assert write_off.lines.get(shortfall__isnull=False).shortfall == Decimal("100.00")

    def test_граммы_с_граммами_не_сломались(self, family, menu):
        """Перевод не должен мешать тем, кто и так сходился."""
        meat = Product.objects.create(name="Плюмбус мясной")
        item = FridgeItem.objects.create(family=family, product=meat, name=meat.name, quantity=Decimal("500"), unit="г")
        dish = _dish(menu, [(meat, 200)])

        write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")

    def test_литры_переводятся_по_плотности(self, family, menu):
        milk = Product.objects.create(name="Молоко плюмбусиное")
        ProductUnitWeight.objects.create(product=milk, unit="л", grams=Decimal("1030"))
        item = FridgeItem.objects.create(family=family, product=milk, name=milk.name, quantity=Decimal("1"), unit="л")
        dish = _dish(menu, [(milk, 515)])

        write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("0.50")


@pytest.mark.django_db
class TestСписокПокупокЧерезПеревод:
    def _names(self, rows):
        return {r["name"] for r in rows}

    def test_яйца_из_холодильника_вычитаются_из_списка(self, family, menu, egg):
        """Раньше они попадали в список, сколько бы их дома ни лежало."""
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))
        FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("30"), unit="шт")
        _dish(menu, [(egg, 100)])

        rows = build_items_from_menu(menu, family, subtract_fridge=True)

        assert egg.name not in self._names(rows)

    def test_без_веса_яйца_остаются_в_списке(self, family, menu, egg):
        FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("30"), unit="шт")
        _dish(menu, [(egg, 100)])

        rows = build_items_from_menu(menu, family, subtract_fridge=True)

        assert egg.name in self._names(rows)

    def test_частичное_покрытие_уменьшает_количество(self, family, menu, egg):
        ProductUnitWeight.objects.create(product=egg, unit="шт", grams=Decimal("50"))
        FridgeItem.objects.create(family=family, product=egg, name=egg.name, quantity=Decimal("1"), unit="шт")
        _dish(menu, [(egg, 150)])

        rows = build_items_from_menu(menu, family, subtract_fridge=True)

        row = next(r for r in rows if r["name"] == egg.name)
        assert row["quantity"] == Decimal("100")
        assert row["unit"] == "г"
