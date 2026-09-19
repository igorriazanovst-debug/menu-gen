"""MG_WRITEOFF: ручка «приготовил» у пункта меню.

Проверяется не только «списалось ли», а то, что отличает ручку от вызова
сервиса напрямую: чьи блюда видны, кому разрешено отмечать, чем первое нажатие
отличается от повторного и что приходит клиенту для экрана нехватки.

Названия продуктов выдуманы: посевная миграция заводит свой каталог в каждую
тестовую базу, и «Помидоры» здесь означали бы вторую запись в выдаче.
"""

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, FridgeWriteOff, Product
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner(db):
    user = User.objects.create_user(email="cooked-owner@example.com", password="pass12345", name="Хозяин")
    _bootstrap_user(user)
    return user


@pytest.fixture
def family(owner):
    return Family.objects.get(owner=owner)


@pytest.fixture
def plumbus(db):
    return Product.objects.create(name="Плюмбус мясной")


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


@pytest.fixture
def dish(menu, plumbus):
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


def _url(dish):
    return f"/api/v1/menu/{dish.menu_id}/items/{dish.id}/cooked/"


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestПриготовил:
    def test_первое_нажатие_списывает(self, owner, dish, fridge_item):
        resp = _client(owner).post(_url(dish))

        assert resp.status_code == 201
        assert resp.data["created"] is True
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")

    def test_в_ответе_видно_что_ушло(self, owner, dish, fridge_item):
        resp = _client(owner).post(_url(dish))

        written = resp.data["written_off"]
        assert len(written) == 1
        assert written[0]["name"] == "Плюмбус мясной"
        assert written[0]["quantity"] == "200.00"
        assert written[0]["unit"] == "г"
        assert resp.data["shortfall"] == []

    def test_нехватка_приходит_отдельным_списком(self, owner, dish, family, plumbus):
        FridgeItem.objects.create(family=family, product=plumbus, name=plumbus.name, quantity=Decimal("50"), unit="г")

        resp = _client(owner).post(_url(dish))

        assert [line["name"] for line in resp.data["written_off"]] == ["Плюмбус мясной"]
        assert resp.data["shortfall"] == [
            {"name": "Плюмбус мясной", "product_id": plumbus.id, "quantity": "150.00", "unit": "г"}
        ]

    def test_повторное_нажатие_не_списывает_второй_раз(self, owner, dish, fridge_item):
        client = _client(owner)
        client.post(_url(dish))

        resp = client.post(_url(dish))

        assert resp.status_code == 200
        assert resp.data["created"] is False
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1


@pytest.mark.django_db
class TestОтмена:
    def test_возвращает_продукты(self, owner, dish, fridge_item):
        client = _client(owner)
        client.post(_url(dish))

        resp = client.delete(_url(dish))

        assert resp.status_code == 204
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")
        assert FridgeWriteOff.objects.count() == 0

    def test_отмена_несписанного_блюда_не_ошибка(self, owner, dish, fridge_item):
        """Две отмены подряд и отмена неотмеченного блюда — одно и то же состояние."""
        resp = _client(owner).delete(_url(dish))

        assert resp.status_code == 204
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")


@pytest.mark.django_db
class TestОтметкаВМеню:
    """Меню должно помнить, что блюдо приготовлено.

    Без этого кнопка врёт: человек закрыл приложение, вернулся — и она снова
    выглядит ненажатой, хотя продукты уже ушли.
    """

    def _item(self, resp, dish):
        return next(i for i in resp.data["items"] if i["id"] == dish.id)

    def test_до_отметки_не_приготовлено(self, owner, dish, fridge_item):
        resp = _client(owner).get(f"/api/v1/menu/{dish.menu_id}/")

        assert self._item(resp, dish)["is_cooked"] is False

    def test_после_отметки_приготовлено(self, owner, dish, fridge_item):
        client = _client(owner)
        client.post(_url(dish))

        resp = client.get(f"/api/v1/menu/{dish.menu_id}/")

        assert self._item(resp, dish)["is_cooked"] is True

    def test_после_отмены_снова_нет(self, owner, dish, fridge_item):
        client = _client(owner)
        client.post(_url(dish))
        client.delete(_url(dish))

        resp = client.get(f"/api/v1/menu/{dish.menu_id}/")

        assert self._item(resp, dish)["is_cooked"] is False

    def test_соседнее_блюдо_не_загорается(self, owner, menu, dish, fridge_item, plumbus):
        """Ключ события — блюдо, а не меню: отметка не должна течь на другие."""
        other = MenuItem.objects.create(
            menu=menu,
            recipe=Recipe.objects.create(title="Другое блюдо", ingredients=[]),
            day_offset=0,
            meal_type=MenuItem.MealType.DINNER,
            meal_slot="dinner",
        )
        client = _client(owner)
        client.post(_url(dish))

        resp = client.get(f"/api/v1/menu/{menu.id}/")

        assert self._item(resp, dish)["is_cooked"] is True
        assert self._item(resp, other)["is_cooked"] is False


@pytest.mark.django_db
class TestДоступ:
    def test_чужое_меню_не_видно(self, dish, fridge_item):
        stranger = User.objects.create_user(email="stranger@example.com", password="pass12345", name="Чужой")
        _bootstrap_user(stranger)

        resp = _client(stranger).post(_url(dish))

        assert resp.status_code == 404
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("500.00")

    def test_отметить_может_не_только_глава_семьи(self, family, dish, fridge_item):
        """Холодильник общий: приготовить блюдо может любой, кто за этим столом.

        Правка меню закрыта для участника (`_can_edit_menu` требует HEAD), но
        «приготовил» — про то, что уже случилось на кухне, а не про состав меню.
        """
        member_user = User.objects.create_user(email="member@example.com", password="pass12345", name="Участник")
        FamilyMember.objects.create(family=family, user=member_user, role=FamilyMember.Role.MEMBER)

        resp = _client(member_user).post(_url(dish))

        assert resp.status_code == 201
        fridge_item.refresh_from_db()
        assert fridge_item.quantity == Decimal("300.00")

    def test_без_авторизации_нельзя(self, dish):
        resp = APIClient().post(_url(dish))

        assert resp.status_code in (401, 403)
