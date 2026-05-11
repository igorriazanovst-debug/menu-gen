"""
MG-605.B: тесты планового FK + is_eaten в DiaryEntry.

- planned_menu_item: OneToOne (один план → один факт)
- is_eaten: default=False (план), True для ручной записи
- planned_menu_item SET_NULL при удалении MenuItem
- сериализатор отдаёт оба поля
- сериализатор пишет оба поля
"""
# MG_605B_V_tests
from __future__ import annotations

import datetime

import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="d605b@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user, name="Семья")
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    recipe = Recipe.objects.create(
        title="Овсянка",
        ingredients=[],
        steps=[],
        nutrition={
            "calories": {"value": "300", "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats":     {"value": "5", "unit": "г"},
            "carbs":    {"value": "50", "unit": "г"},
        },
        is_published=True,
    )
    menu = Menu.objects.create(
        family=family,
        creator_id=user.id,
        period_days=1,
        start_date=datetime.date.today(),
        end_date=datetime.date.today(),
        status=Menu.Status.ACTIVE,
    )
    menu_item = MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        member=member,
        meal_type="breakfast",
        meal_slot="breakfast",
        day_offset=0,
        component_role="grain",
    )
    return user, member, recipe, menu_item


# ─────────────────────────── unit: модель ─────────────────────────────────────

@pytest.mark.django_db
class TestDiaryEntryFields:
    def test_default_is_eaten_false(self, setup):
        user, member, recipe, _ = setup
        e = DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
        )
        assert e.is_eaten is False
        assert e.planned_menu_item is None

    def test_can_attach_planned_menu_item(self, setup):
        user, member, recipe, menu_item = setup
        e = DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
            planned_menu_item=menu_item, is_eaten=False,
        )
        assert e.planned_menu_item_id == menu_item.id
        assert e.is_eaten is False

    def test_set_is_eaten_true(self, setup):
        user, member, recipe, menu_item = setup
        e = DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
            planned_menu_item=menu_item, is_eaten=True,
        )
        assert e.is_eaten is True


# ─────────────────────────── unit: уникальность OneToOne ──────────────────────

@pytest.mark.django_db
class TestOneToOneConstraint:
    def test_cannot_attach_twice_same_menu_item(self, setup):
        user, member, recipe, menu_item = setup
        DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
            planned_menu_item=menu_item,
        )
        with pytest.raises(IntegrityError):
            DiaryEntry.objects.create(
                member=member, date=datetime.date.today(),
                meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
                planned_menu_item=menu_item,
            )

    def test_two_entries_with_null_planned_item_allowed(self, setup):
        user, member, recipe, _ = setup
        DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
        )
        # Вторая без планового пункта — должна создаваться без ошибок
        DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="snack", custom_name="Орех", nutrition={}, quantity=1,
        )
        assert DiaryEntry.objects.count() == 2


# ─────────────────────────── unit: SET_NULL при удалении MenuItem ─────────────

@pytest.mark.django_db
class TestSetNullOnMenuItemDelete:
    def test_diary_entry_keeps_when_menu_item_deleted(self, setup):
        user, member, recipe, menu_item = setup
        e = DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
            planned_menu_item=menu_item, is_eaten=True,
        )
        eid = e.id
        menu_item.delete()
        e.refresh_from_db()
        assert e.id == eid
        assert e.planned_menu_item is None
        assert e.is_eaten is True  # факт остался


# ─────────────────────────── API: сериализатор отдаёт новые поля ──────────────

@pytest.mark.django_db
class TestSerializerExposesFields:
    def test_get_returns_planned_and_is_eaten(self, client, setup):
        user, member, recipe, menu_item = setup
        DiaryEntry.objects.create(
            member=member, date=datetime.date.today(),
            meal_type="breakfast", recipe=recipe, nutrition={}, quantity=1,
            planned_menu_item=menu_item, is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-list"), {"date": str(datetime.date.today())})
        assert resp.status_code == 200
        item = resp.data["results"][0]
        assert item["planned_menu_item"] == menu_item.id
        assert item["is_eaten"] is False

    def test_post_can_set_planned_and_is_eaten(self, client, setup):
        user, member, recipe, menu_item = setup
        client.force_authenticate(user)
        resp = client.post(
            reverse("diary-list"),
            {
                "date": str(datetime.date.today()),
                "meal_type": "breakfast",
                "recipe": recipe.id,
                "quantity": 1,
                "planned_menu_item": menu_item.id,
                "is_eaten": True,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["planned_menu_item"] == menu_item.id
        assert resp.data["is_eaten"] is True

    def test_post_default_is_eaten_false(self, client, setup):
        user, member, recipe, _ = setup
        client.force_authenticate(user)
        resp = client.post(
            reverse("diary-list"),
            {
                "date": str(datetime.date.today()),
                "meal_type": "breakfast",
                "recipe": recipe.id,
                "quantity": 1,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["is_eaten"] is False
