"""MG_WRITEOFF: списание продуктов из холодильника при «приготовил».

Холодильник до сих пор только пополнялся: купленное в него перекладывалось, а
убирать приходилось руками. Съеденное оставалось, и на этом расхождении стоит
список покупок — он вычитает из потребности то, что «лежит дома». Фарш,
съеденный неделю назад, честно вычитался и в список не попадал.

Проверяется не «уменьшилось ли число», а границы, на которых это ломается:
единицы (кг против г), несколько позиций одного продукта, нехватка, повторная
отметка тремя участниками, отмена.

Названия выдуманы: посевная миграция заводит свой каталог в каждую тестовую базу.
"""

import datetime
from decimal import Decimal

import pytest

from apps.family.models import Family
from apps.fridge.models import FridgeItem, FridgeWriteOff, Product
from apps.fridge.writeoff import undo_write_off, write_off_menu_item
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def family(db):
    owner = User.objects.create_user(email="writeoff@example.com", password="pass12345", name="Owner")
    _bootstrap_user(owner)
    return Family.objects.get(owner=owner)


@pytest.fixture
def menu(family):
    today = datetime.date.today()
    return Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )


def _dish(menu, links, *, member=None, title="Тестовое блюдо"):
    """Рецепт со связями и пункт меню для него."""
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
        member=member,
        day_offset=0,
        meal_type=MenuItem.MealType.LUNCH,
        meal_slot="lunch",
    )


def _fridge(family, product, qty, unit, **kwargs):
    return FridgeItem.objects.create(
        family=family, product=product, name=product.name, quantity=Decimal(str(qty)), unit=unit, **kwargs
    )


@pytest.mark.django_db
class TestСписание:
    def test_списывается_столько_сколько_нужно_блюду(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 500, "г")
        dish = _dish(menu, [(plumbus, 200)])

        write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")
        assert item.is_deleted is False

    def test_единицы_переводятся(self, family, menu):
        """В холодильнике килограмм, в рецепте граммы — это одно и то же."""
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 1, "кг")
        dish = _dish(menu, [(plumbus, 250)])

        write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("0.75")
        assert item.unit == "кг"

    def test_позиция_уходит_в_ноль_и_скрывается(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 200, "г")
        dish = _dish(menu, [(plumbus, 200)])

        write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("0.00")
        assert item.is_deleted is True

    def test_списывается_сначала_то_что_раньше_испортится(self, family, menu):
        """Иначе человек достанет свежее, а приложение спишет старое."""
        plumbus = Product.objects.create(name="Плюмбус мясной")
        today = datetime.date.today()
        old = _fridge(family, plumbus, 300, "г", expiry_date=today + datetime.timedelta(days=1))
        fresh = _fridge(family, plumbus, 300, "г", expiry_date=today + datetime.timedelta(days=10))
        dish = _dish(menu, [(plumbus, 300)])

        write_off_menu_item(dish)

        old.refresh_from_db()
        fresh.refresh_from_db()
        assert old.is_deleted is True
        assert fresh.quantity == Decimal("300.00")

    def test_нужное_собирается_из_нескольких_позиций(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        a = _fridge(family, plumbus, 200, "г")
        b = _fridge(family, plumbus, 200, "г")
        dish = _dish(menu, [(plumbus, 300)])

        write_off_menu_item(dish)

        a.refresh_from_db()
        b.refresh_from_db()
        assert {a.quantity, b.quantity} == {Decimal("0.00"), Decimal("100.00")}


@pytest.mark.django_db
class TestНехватка:
    def test_нехватка_записывается_строкой(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        _fridge(family, plumbus, 100, "г")
        dish = _dish(menu, [(plumbus, 300)])

        write_off, _ = write_off_menu_item(dish)

        short = write_off.lines.filter(fridge_item__isnull=True)
        assert short.count() == 1
        assert short.first().shortfall == Decimal("200.00")
        assert short.first().shortfall_unit == "г"

    def test_когда_в_холодильнике_нет_ничего(self, family, menu):
        """Стопроцентная нехватка — тот же случай, только целиком."""
        plumbus = Product.objects.create(name="Плюмбус мясной")
        dish = _dish(menu, [(plumbus, 300)])

        write_off, created = write_off_menu_item(dish)

        assert created is True
        assert write_off.lines.count() == 1
        assert write_off.lines.first().shortfall == Decimal("300.00")

    def test_чужой_холодильник_не_трогаем(self, family, menu):
        other_owner = User.objects.create_user(email="other@example.com", password="pass12345", name="Чужой")
        _bootstrap_user(other_owner)
        other = Family.objects.get(owner=other_owner)
        plumbus = Product.objects.create(name="Плюмбус мясной")
        theirs = _fridge(other, plumbus, 500, "г")
        dish = _dish(menu, [(plumbus, 200)])

        write_off_menu_item(dish)

        theirs.refresh_from_db()
        assert theirs.quantity == Decimal("500.00")


@pytest.mark.django_db
class TestОдноБлюдоОдноСписание:
    def test_повторная_отметка_ничего_не_списывает(self, family, menu):
        """Трое отметили «съел» одно блюдо — списание одно."""
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 500, "г")
        dish = _dish(menu, [(plumbus, 200)])

        first, created_first = write_off_menu_item(dish)
        second, created_second = write_off_menu_item(dish)

        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")
        assert created_first is True
        assert created_second is False
        assert first.id == second.id
        assert FridgeWriteOff.objects.count() == 1

    def test_у_каждого_участника_свой_пункт_но_блюдо_одно(self, family, menu):
        """Пункт меню принадлежит участнику: одно блюдо на троих — три пункта."""
        from apps.family.models import FamilyMember

        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 500, "г")
        recipe = Recipe.objects.create(title="Общее блюдо", ingredients=[])
        RecipeProduct.objects.create(
            recipe=recipe, name_canonical=plumbus.name, name_raw="плюмбус", product=plumbus, grams=200
        )
        items = []
        for i in range(3):
            eater = User.objects.create_user(email="eater%d@example.com" % i, password="pass12345", name="Едок %d" % i)
            member = FamilyMember.objects.create(family=family, user=eater)
            items.append(
                MenuItem.objects.create(
                    menu=menu,
                    recipe=recipe,
                    member=member,
                    day_offset=0,
                    meal_type=MenuItem.MealType.LUNCH,
                    meal_slot="lunch",
                )
            )

        for mi in items:
            write_off_menu_item(mi)

        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1


@pytest.mark.django_db
class TestОтмена:
    def test_возвращается_ровно_то_что_ушло(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 1, "кг")
        dish = _dish(menu, [(plumbus, 250)])
        write_off, _ = write_off_menu_item(dish)

        undo_write_off(write_off)

        item.refresh_from_db()
        assert item.quantity == Decimal("1.00")
        assert FridgeWriteOff.objects.count() == 0

    def test_позиция_ушедшая_в_ноль_возвращается(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 200, "г")
        dish = _dish(menu, [(plumbus, 200)])
        write_off, _ = write_off_menu_item(dish)

        undo_write_off(write_off)

        item.refresh_from_db()
        assert item.quantity == Decimal("200.00")
        assert item.is_deleted is False

    def test_после_отмены_можно_списать_снова(self, family, menu):
        plumbus = Product.objects.create(name="Плюмбус мясной")
        item = _fridge(family, plumbus, 500, "г")
        dish = _dish(menu, [(plumbus, 200)])
        write_off, _ = write_off_menu_item(dish)
        undo_write_off(write_off)

        _, created = write_off_menu_item(dish)

        item.refresh_from_db()
        assert created is True
        assert item.quantity == Decimal("300.00")
