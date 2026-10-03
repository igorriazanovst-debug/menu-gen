"""MG_ITEMDEL: убрать блюдо из меню.

Выходов было два — заменить блюдо или удалить меню целиком. Между ними ничего,
а нужно именно это: «не буду я во вторник суп».

Удаление сдвигает баланс дня, и это не причина запрещать — заменой меню и так
правится. Клиентам отдаётся `modified_by`, чтобы они могли сказать, что меню
тронуто руками и цифры генератора больше не те.

Чего делать нельзя — удалять приготовленное блюдо. Событие списания привязано к
блюду (меню, день, приём, рецепт), а не к пункту меню: удалив пункт, мы оставим
списание без блюда, и отменить его станет нечем. Продукты ушли бы молча и
навсегда.

Названия выдуманы: посевная миграция заводит каталог продуктов в каждую
тестовую базу.
"""

from __future__ import annotations

import datetime

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeWriteOff
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.users.models import Profile, User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db, grant_premium):
    user = User.objects.create_user(email="itemdel@example.com", name="Хозяин", password="pass12345")
    Profile.objects.create(user=user, birth_year=1985, calorie_target=2200)
    family = Family.objects.create(owner=user, name="Семья")
    grant_premium(family)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)

    today = datetime.date.today()
    menu = Menu.objects.create(
        family=family,
        creator_id=user.id,
        start_date=today,
        end_date=today + datetime.timedelta(days=6),
        status=Menu.Status.ACTIVE,
    )
    recipe = Recipe.objects.create(title="Суп плюмбусный", ingredients=[], is_published=True)
    item = MenuItem.objects.create(
        menu=menu,
        member=member,
        recipe=recipe,
        day_offset=1,
        meal_type=MenuItem.MealType.LUNCH,
        meal_slot="lunch",
        component_role="soup",
    )
    return {"user": user, "family": family, "menu": menu, "item": item, "recipe": recipe}


def _url(menu, item):
    return f"/api/v1/menu/{menu.id}/items/{item.id}/"


@pytest.mark.django_db
class TestУдалениеБлюда:
    def test_блюдо_удаляется(self, client, setup):
        client.force_authenticate(setup["user"])

        resp = client.delete(_url(setup["menu"], setup["item"]))

        assert resp.status_code == 204
        assert not MenuItem.objects.filter(id=setup["item"].id).exists()

    def test_меню_помечается_тронутым_руками(self, client, setup):
        """Иначе клиенту нечем сказать, что цифры генератора больше не те."""
        client.force_authenticate(setup["user"])

        client.delete(_url(setup["menu"], setup["item"]))

        setup["menu"].refresh_from_db()
        assert setup["menu"].modified_by == Menu.ModifiedBy.USER

    def test_метка_видна_в_выдаче_меню(self, client, setup):
        client.force_authenticate(setup["user"])
        client.delete(_url(setup["menu"], setup["item"]))

        resp = client.get(f"/api/v1/menu/{setup['menu'].id}/")

        assert resp.status_code == 200
        assert resp.data["modified_by"] == "user"

    def test_остальные_блюда_не_трогаются(self, client, setup):
        other = MenuItem.objects.create(
            menu=setup["menu"],
            member=setup["item"].member,
            recipe=setup["recipe"],
            day_offset=1,
            meal_type=MenuItem.MealType.LUNCH,
            meal_slot="lunch",
            component_role="main",
        )
        client.force_authenticate(setup["user"])

        client.delete(_url(setup["menu"], setup["item"]))

        assert MenuItem.objects.filter(id=other.id).exists()


@pytest.mark.django_db
class TestПриготовленноеНеУдаляем:
    def test_приготовленное_блюдо_удалить_нельзя(self, client, setup):
        """Списание привязано к блюду: удалив пункт, отменить его станет нечем."""
        FridgeWriteOff.objects.create(
            family=setup["family"],
            menu=setup["menu"],
            recipe=setup["recipe"],
            day_offset=1,
            meal_slot="lunch",
        )
        client.force_authenticate(setup["user"])

        resp = client.delete(_url(setup["menu"], setup["item"]))

        assert resp.status_code == 409
        assert resp.data["code"] == "item_cooked"
        assert MenuItem.objects.filter(id=setup["item"].id).exists()

    def test_после_отмены_приготовления_удаляется(self, client, setup):
        wo = FridgeWriteOff.objects.create(
            family=setup["family"],
            menu=setup["menu"],
            recipe=setup["recipe"],
            day_offset=1,
            meal_slot="lunch",
        )
        client.force_authenticate(setup["user"])
        assert client.delete(_url(setup["menu"], setup["item"])).status_code == 409

        wo.delete()  # то же делает «отменить приготовление»

        assert client.delete(_url(setup["menu"], setup["item"])).status_code == 204

    def test_списание_другого_блюда_не_мешает(self, client, setup):
        """Ключ списания — блюдо целиком, а не только рецепт."""
        FridgeWriteOff.objects.create(
            family=setup["family"],
            menu=setup["menu"],
            recipe=setup["recipe"],
            day_offset=5,  # другой день
            meal_slot="lunch",
        )
        client.force_authenticate(setup["user"])

        assert client.delete(_url(setup["menu"], setup["item"])).status_code == 204


@pytest.mark.django_db
class TestПрава:
    def test_чужое_меню_не_удаляется(self, client, setup, grant_premium):
        stranger = User.objects.create_user(email="stranger-itemdel@example.com", name="Сосед", password="pass12345")
        Profile.objects.create(user=stranger, birth_year=1990)
        other_family = Family.objects.create(owner=stranger, name="Чужая семья")
        grant_premium(other_family)  # премиум есть — проверяем владение, а не тариф
        FamilyMember.objects.create(family=other_family, user=stranger, role=FamilyMember.Role.HEAD)
        client.force_authenticate(stranger)

        resp = client.delete(_url(setup["menu"], setup["item"]))

        assert resp.status_code == 404
        assert MenuItem.objects.filter(id=setup["item"].id).exists()

    def test_без_входа_нельзя(self, client, setup):
        resp = client.delete(_url(setup["menu"], setup["item"]))

        assert resp.status_code in (401, 403)
        assert MenuItem.objects.filter(id=setup["item"].id).exists()
