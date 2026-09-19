"""MG_WRITEOFF: отметка «съел» у блюда из меню списывает продукты.

Логика, о которой договорились: если человек ест блюдо из меню, значит его
кто-то приготовил, а продукты на него ушли. Отдельной кнопки «приготовил» для
этого не требуется — дневник её подразумевает.

Обратное неверно и проверяется здесь же: снятие галочки списание не отменяет.
Передумать записывать съеденное можно, вернуть продукты в холодильник —
нет. Отмена — отдельное действие на самом блюде.

Всё это живёт за флагом MG_WRITEOFF_ON_EATEN и по умолчанию выключено: пока в
опубликованном приложении нет кнопок «приготовил» и «отменить», списание по
отметке в дневнике для человека молчаливое и необратимое. Поэтому тесты флаг
включают явно, а отдельный класс проверяет выключенное состояние.

Названия продуктов выдуманы: посевная миграция заводит каталог в каждую
тестовую базу.
"""

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family
from apps.fridge.models import FridgeItem, FridgeWriteOff, Product
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner(db):
    user = User.objects.create_user(email="eaten@example.com", password="pass12345", name="Едок")
    _bootstrap_user(user)
    return user


@pytest.fixture
def family(owner, grant_premium):
    family = Family.objects.get(owner=owner)
    # Дневник бесплатен, но тест дёргает и ручку меню — ей нужен премиум.
    grant_premium(family)
    return family


@pytest.fixture
def member(family, owner):
    return family.members.get(user=owner)


@pytest.fixture
def plumbus(db):
    return Product.objects.create(name="Плюмбус мясной")


@pytest.fixture
def dish(family, owner, plumbus):
    today = datetime.date.today()
    menu = Menu.objects.create(
        family=family,
        creator_id=owner.id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )
    recipe = Recipe.objects.create(title="Блюдо с плюмбусом", ingredients=[])
    RecipeProduct.objects.create(
        recipe=recipe,
        name_canonical=plumbus.name,
        name_raw=plumbus.name.lower(),
        product=plumbus,
        grams=200,
    )
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        day_offset=0,
        meal_type=MenuItem.MealType.LUNCH,
        meal_slot="lunch",
    )


@pytest.fixture
def fridge_item(family, plumbus):
    return FridgeItem.objects.create(
        family=family, product=plumbus, name=plumbus.name, quantity=Decimal("500"), unit="г"
    )


@pytest.fixture
def planned(owner, member, dish):
    return DiaryEntry.objects.create(
        user=owner,
        member=member,
        date=datetime.date.today(),
        meal_type=dish.meal_type,
        meal_slot=dish.meal_slot,
        recipe=dish.recipe,
        planned_menu_item=dish,
        nutrition={},
        quantity=1,
        is_eaten=False,
        is_planned=True,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture(autouse=True)
def включённый_флаг(settings):
    """Списание по «съел» включено — иначе проверять было бы нечего."""
    settings.MG_WRITEOFF_ON_EATEN = True


@pytest.mark.django_db
class TestОтметкаСъел:
    def test_галочка_списывает_продукты(self, owner, planned, fridge_item):
        resp = _client(owner).patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        assert resp.status_code == 200
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1

    def test_правка_записи_без_галочки_ничего_не_списывает(self, owner, planned, fridge_item):
        resp = _client(owner).patch(f"/api/v1/diary/{planned.id}/", {"quantity": "2"}, format="json")

        assert resp.status_code == 200
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")
        assert FridgeWriteOff.objects.count() == 0

    def test_повторная_галочка_не_списывает_второй_раз(self, owner, planned, fridge_item):
        client = _client(owner)
        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True, "quantity": "2"}, format="json")

        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1

    def test_ручная_запись_без_плана_ничего_не_списывает(self, owner, member, fridge_item):
        """Съеденное вне меню про холодильник ничего не говорит: что человек
        съел в гостях, дома не лежало."""
        entry = DiaryEntry.objects.create(
            user=owner,
            member=member,
            date=datetime.date.today(),
            meal_type="lunch",
            custom_name="Шаурма у метро",
            nutrition={},
            quantity=1,
            is_eaten=False,
        )

        _client(owner).patch(f"/api/v1/diary/{entry.id}/", {"is_eaten": True}, format="json")

        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")
        assert FridgeWriteOff.objects.count() == 0


@pytest.mark.django_db
class TestСнятиеГалочки:
    def test_снятие_не_возвращает_продукты(self, owner, planned, fridge_item):
        client = _client(owner)
        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": False}, format="json")

        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1

    def test_галочка_после_снятия_не_списывает_ещё_раз(self, owner, planned, fridge_item):
        client = _client(owner)
        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")
        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": False}, format="json")

        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1


@pytest.mark.django_db
class TestОдноБлюдоОдноСписание:
    def test_ручка_приготовил_и_дневник_не_складываются(self, owner, planned, dish, fridge_item):
        """Отметил «приготовил», потом «съел» — списание одно.

        Обе дороги ведут в один сервис и считают один и тот же ключ блюда,
        иначе холодильник уходил бы в минус на каждом обеде.
        """
        client = _client(owner)
        client.post(f"/api/v1/menu/{dish.menu_id}/items/{dish.id}/cooked/")

        client.patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1


@pytest.mark.django_db
class TestФлагВыключен:
    """По умолчанию списание по отметке в дневнике выключено.

    Дневник есть в уже опубликованном приложении, а кнопок «приготовил» и
    «отменить списание» в нём нет. Включённое списание означало бы, что у людей
    убывают продукты без видимой причины и без способа это отменить.
    """

    def test_галочка_ничего_не_списывает(self, owner, planned, fridge_item, settings):
        settings.MG_WRITEOFF_ON_EATEN = False

        resp = _client(owner).patch(f"/api/v1/diary/{planned.id}/", {"is_eaten": True}, format="json")

        assert resp.status_code == 200
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")
        assert FridgeWriteOff.objects.count() == 0

    def test_кнопка_приготовил_от_флага_не_зависит(self, owner, dish, fridge_item, settings):
        """Там человек нажал сам и сразу видит, что ушло, — прятать нечего."""
        settings.MG_WRITEOFF_ON_EATEN = False

        resp = _client(owner).post(f"/api/v1/menu/{dish.menu_id}/items/{dish.id}/cooked/")

        assert resp.status_code == 201
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
