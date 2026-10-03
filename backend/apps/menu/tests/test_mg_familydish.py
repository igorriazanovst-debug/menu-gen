"""MG_FAMILYDISH: замена и удаление работают с блюдом, а не с записью человека.

В режиме «одно меню на всю семью» блюдо хранится по записи на каждого члена:
одинаковые день, приём, роль и рецепт, разный только `member`. Клиенты рисуют
такую пачку ОДНОЙ карточкой — и веб, и приложение склеивают позиции по рецепту
сознательно, иначе обед на троих показывал бы девять карточек вместо трёх.

Пока замена правила одну запись, у остальных членов семьи оставалось старое
блюдо, и склеенная пара расклеивалась. С прода это пришло так: в обеде было
четыре карточки, человек заменил бобовое блюдо на картофель с грибами — и стало
пять. Пятым был картофель, четвёртым осталось «Лобио» у второго члена семьи.
Выглядело как «замена добавила блюдо», хотя добавления не было.

В режиме «каждому своё» блюда у членов семьи разные по смыслу — там замена
обязана остаться на одной записи.

Названия выдуманы: посевная миграция заводит каталог продуктов в каждую
тестовую базу.
"""

from __future__ import annotations

import datetime

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.users.models import Profile, User


@pytest.fixture
def client():
    return APIClient()


def _menu_with_two_members(grant_premium, mode):
    """Семья из двух человек и обед, в котором одно блюдо на двоих."""
    owner = User.objects.create_user(email=f"famdish-{mode}@example.com", name="Глава", password="pass12345")
    Profile.objects.create(user=owner, birth_year=1985, calorie_target=2400)
    spouse = User.objects.create_user(email=f"famdish-{mode}-2@example.com", name="Супруга", password="pass12345")
    Profile.objects.create(user=spouse, birth_year=1990, calorie_target=2000)

    family = Family.objects.create(owner=owner, name="Семья")
    grant_premium(family)
    m1 = FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    m2 = FamilyMember.objects.create(family=family, user=spouse, role=FamilyMember.Role.MEMBER)

    today = datetime.date.today()
    menu = Menu.objects.create(
        family=family,
        creator_id=owner.id,
        start_date=today,
        end_date=today + datetime.timedelta(days=1),
        status=Menu.Status.ACTIVE,
        filters_used={"mode": mode},
    )
    old = Recipe.objects.create(title="Лобио плюмбусное", ingredients=[], is_published=True, food_group="protein")
    new = Recipe.objects.create(title="Картофель плюмбусный", ingredients=[], is_published=True, food_group="protein")

    items = [
        MenuItem.objects.create(
            menu=menu,
            member=member,
            recipe=old,
            day_offset=0,
            meal_type=MenuItem.MealType.LUNCH,
            meal_slot="lunch",
            component_role="main",
        )
        for member in (m1, m2)
    ]
    return {"user": owner, "family": family, "menu": menu, "items": items, "old": old, "new": new}


@pytest.fixture
def family_menu(db, grant_premium):
    return _menu_with_two_members(grant_premium, "family")


@pytest.fixture
def per_member_menu(db, grant_premium):
    return _menu_with_two_members(grant_premium, "per_member")


def _url(menu, item):
    return f"/api/v1/menu/{menu.id}/items/{item.id}/"


@pytest.mark.django_db
class TestЗаменаВСемейномМеню:
    def test_блюдо_меняется_у_всех(self, client, family_menu):
        """Иначе склеенная карточка расклеивается, и это читается как «добавилось»."""
        client.force_authenticate(family_menu["user"])
        first, second = family_menu["items"]

        resp = client.patch(_url(family_menu["menu"], first), {"recipe_id": family_menu["new"].id}, format="json")

        assert resp.status_code == 200
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.recipe_id == family_menu["new"].id
        assert second.recipe_id == family_menu["new"].id

    def test_число_блюд_в_приёме_не_растёт(self, client, family_menu):
        client.force_authenticate(family_menu["user"])
        before = MenuItem.objects.filter(menu=family_menu["menu"], meal_slot="lunch").count()

        client.patch(
            _url(family_menu["menu"], family_menu["items"][0]),
            {"recipe_id": family_menu["new"].id},
            format="json",
        )

        after = MenuItem.objects.filter(menu=family_menu["menu"], meal_slot="lunch").count()
        assert after == before
        # И блюдо в приёме теперь одно, а не два разных.
        assert (
            MenuItem.objects.filter(menu=family_menu["menu"], meal_slot="lunch").values("recipe_id").distinct().count()
            == 1
        )

    def test_другой_приём_не_трогается(self, client, family_menu):
        dinner = MenuItem.objects.create(
            menu=family_menu["menu"],
            member=family_menu["items"][0].member,
            recipe=family_menu["old"],
            day_offset=0,
            meal_type=MenuItem.MealType.DINNER,
            meal_slot="dinner",
            component_role="main",
        )
        client.force_authenticate(family_menu["user"])

        client.patch(
            _url(family_menu["menu"], family_menu["items"][0]),
            {"recipe_id": family_menu["new"].id},
            format="json",
        )

        dinner.refresh_from_db()
        assert dinner.recipe_id == family_menu["old"].id

    def test_другая_роль_не_трогается(self, client, family_menu):
        salad = MenuItem.objects.create(
            menu=family_menu["menu"],
            member=family_menu["items"][0].member,
            recipe=family_menu["old"],
            day_offset=0,
            meal_type=MenuItem.MealType.LUNCH,
            meal_slot="lunch",
            component_role="salad",
        )
        client.force_authenticate(family_menu["user"])

        client.patch(
            _url(family_menu["menu"], family_menu["items"][0]),
            {"recipe_id": family_menu["new"].id},
            format="json",
        )

        salad.refresh_from_db()
        assert salad.recipe_id == family_menu["old"].id


@pytest.mark.django_db
class TestЗаменаВМенюКаждомуСвоё:
    def test_меняется_только_своё_блюдо(self, client, per_member_menu):
        """Здесь блюда у людей разные по смыслу — чужое трогать нельзя."""
        client.force_authenticate(per_member_menu["user"])
        first, second = per_member_menu["items"]

        client.patch(_url(per_member_menu["menu"], first), {"recipe_id": per_member_menu["new"].id}, format="json")

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.recipe_id == per_member_menu["new"].id
        assert second.recipe_id == per_member_menu["old"].id


@pytest.mark.django_db
class TestУдалениеВСемейномМеню:
    def test_блюдо_убирается_у_всех(self, client, family_menu):
        client.force_authenticate(family_menu["user"])
        first, second = family_menu["items"]

        resp = client.delete(_url(family_menu["menu"], first))

        assert resp.status_code == 204
        assert not MenuItem.objects.filter(id__in=[first.id, second.id]).exists()

    def test_в_меню_каждому_своё_убирается_одно(self, client, per_member_menu):
        client.force_authenticate(per_member_menu["user"])
        first, second = per_member_menu["items"]

        client.delete(_url(per_member_menu["menu"], first))

        assert not MenuItem.objects.filter(id=first.id).exists()
        assert MenuItem.objects.filter(id=second.id).exists()
