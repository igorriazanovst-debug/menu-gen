#!/usr/bin/env bash
# MG-605.A tests: тесты для mode=per_member/family
set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TEST="$ROOT/backend/apps/menu/tests/test_mg_605a_mode.py"

echo "[1] Создаю $TEST"
cat > "$TEST" <<'PYEOF'
"""
MG-605.A: тесты режима мульти-член (per_member / family).

- per_member: для каждого члена свой набор рецептов
- family: единое меню, один набор рецептов, разные quantity per member
- mode по умолчанию = family
- mode=family + 1 член семьи → ведёт себя как per_member (нет смысла дублировать)
- union allergies/disliked в family-режиме
- средний calorie_target в family-режиме
"""
# MG_605A_V_tests
from __future__ import annotations

import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.generator import MenuGenerator
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.users.models import Profile, User


# ─────────────────────────── fixtures ─────────────────────────────────────────

@pytest.fixture
def client():
    return APIClient()


def _make_recipe(title, food_group="vegetable", calories=300, weight_g=200,
                 is_published=True, **extra):
    return Recipe.objects.create(
        title=title,
        ingredients=[{"name": "Ингредиент", "quantity": "100", "unit": "г"}],
        steps=[{"text": "Шаг 1"}],
        nutrition={
            "calories": {"value": str(calories), "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats":     {"value": "5", "unit": "г"},
            "carbs":    {"value": "30", "unit": "г"},
            "weight":   {"value": str(weight_g), "unit": "г"},
        },
        is_published=is_published,
        food_group=food_group,
        **extra,
    )


@pytest.fixture
def family_with_three(db):
    """Семья из 3 человек: глава + 2 участника, разный возраст."""
    head_user = User.objects.create_user(email="head605@example.com", name="Глава", password="pass1234")
    Profile.objects.create(user=head_user, birth_year=1985, calorie_target=2400)

    mem1 = User.objects.create_user(email="m1@example.com", name="Жена", password="pass1234")
    Profile.objects.create(user=mem1, birth_year=1990, calorie_target=2000)

    kid = User.objects.create_user(email="kid@example.com", name="Ребёнок", password="pass1234")
    Profile.objects.create(user=kid, birth_year=2016, calorie_target=1500)  # ~9 лет

    family = Family.objects.create(owner=head_user, name="Семья")
    head_m = FamilyMember.objects.create(family=family, user=head_user, role=FamilyMember.Role.HEAD)
    mem_m = FamilyMember.objects.create(family=family, user=mem1, role=FamilyMember.Role.MEMBER)
    kid_m = FamilyMember.objects.create(family=family, user=kid, role=FamilyMember.Role.MEMBER)

    # Базовый пул рецептов разных ролей (по food_group)
    for i in range(20):
        _make_recipe(f"Прот {i}", food_group="meat", calories=400)
    for i in range(20):
        _make_recipe(f"Крупа {i}", food_group="grain", calories=350)
    for i in range(20):
        _make_recipe(f"Овощ {i}", food_group="vegetable", calories=80)
    for i in range(10):
        _make_recipe(f"Фрукт {i}", food_group="fruit", calories=120)
    for i in range(10):
        _make_recipe(f"Молоко {i}", food_group="dairy", calories=150)

    return family, [head_m, mem_m, kid_m]


@pytest.fixture
def family_solo(db):
    """Семья из 1 человека."""
    user = User.objects.create_user(email="solo605@example.com", name="Один", password="pass1234")
    Profile.objects.create(user=user, birth_year=1985, calorie_target=2200)
    family = Family.objects.create(owner=user, name="Сам")
    head = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)

    for i in range(20):
        _make_recipe(f"Прот {i}", food_group="meat", calories=400)
    for i in range(20):
        _make_recipe(f"Крупа {i}", food_group="grain", calories=350)
    for i in range(20):
        _make_recipe(f"Овощ {i}", food_group="vegetable", calories=80)
    for i in range(10):
        _make_recipe(f"Фрукт {i}", food_group="fruit", calories=120)
    for i in range(10):
        _make_recipe(f"Молоко {i}", food_group="dairy", calories=150)
    return family, [head]


# ─────────────────────────── unit: MenuGenerator ──────────────────────────────

@pytest.mark.django_db
class TestModeFlag:
    def test_default_mode_is_family(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free", filters={})
        assert gen.mode == "family"

    def test_explicit_per_member(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "per_member"})
        assert gen.mode == "per_member"

    def test_invalid_mode_falls_back_to_family(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "bogus"})
        assert gen.mode == "family"


@pytest.mark.django_db
class TestModeFamily:
    """Режим family: один набор рецептов, items для каждого члена."""

    def test_family_one_recipe_per_role_slot(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=2,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "family"})
        items = gen.generate()

        # На каждый (day, meal_slot, component_role) — ОДИН recipe.id (общий)
        groups = {}
        for it in items:
            if it.get("is_virtual"):
                continue
            k = (it["day_offset"], it["meal_slot"], it["component_role"])
            groups.setdefault(k, set()).add(it["recipe"].id)
        for k, rids in groups.items():
            assert len(rids) == 1, f"family mode: на {k} должен быть 1 рецепт, а получили {rids}"

    def test_family_item_per_member(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "family"})
        items = gen.generate()

        # На каждый (day, meal_slot, component_role) — items для всех 3 членов
        groups = {}
        for it in items:
            if it.get("is_virtual"):
                continue
            k = (it["day_offset"], it["meal_slot"], it["component_role"])
            groups.setdefault(k, set()).add(it["member"].id)
        member_ids = {m.id for m in members}
        for k, mids in groups.items():
            assert mids == member_ids, f"family mode: на {k} должны быть все члены, есть {mids}"

    def test_family_quantity_scales_by_age(self, family_with_three):
        family, members = family_with_three
        head, wife, kid = members
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "family"})
        items = gen.generate()

        # Возьмём первый item для каждого члена — его quantity
        per_member = {}
        for it in items:
            if it.get("is_virtual"):
                continue
            per_member.setdefault(it["member"].id, []).append(float(it.get("quantity", 1)))

        # Взрослые 1.0, ребёнок ~0.70 (7-10 лет в _age_multiplier)
        head_q = per_member[head.id][0]
        wife_q = per_member[wife.id][0]
        kid_q = per_member[kid.id][0]
        assert head_q == pytest.approx(1.0, abs=0.01)
        assert wife_q == pytest.approx(1.0, abs=0.01)
        assert kid_q == pytest.approx(0.70, abs=0.01)

    def test_family_solo_member_no_dup(self, family_solo):
        """Семья из 1 человека: family-режим не должен дублировать."""
        family, members = family_solo
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "family"})
        items = gen.generate()

        # Один член — items только под него
        for it in items:
            assert it["member"].id == members[0].id


@pytest.mark.django_db
class TestModePerMember:
    """Режим per_member: каждый член — отдельный прогон, рецепты могут различаться."""

    def test_per_member_items_per_member(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="free",
                            filters={"mode": "per_member"})
        items = gen.generate()

        # На каждый (day, meal_slot, component_role) — items для всех 3 членов
        groups = {}
        for it in items:
            if it.get("is_virtual"):
                continue
            k = (it["day_offset"], it["meal_slot"], it["component_role"])
            groups.setdefault(k, set()).add(it["member"].id)
        member_ids = {m.id for m in members}
        for k, mids in groups.items():
            assert mids == member_ids


# ─────────────────────────── virtual member: union ────────────────────────────

@pytest.mark.django_db
class TestFamilyVirtualMember:
    def test_union_allergies(self, family_with_three):
        family, members = family_with_three
        # Назначим разные аллергии
        members[0].user.allergies = ["орех"]
        members[0].user.save()
        members[1].user.allergies = ["молоко"]
        members[1].user.save()
        members[2].user.allergies = []
        members[2].user.save()

        # premium для allergies_family
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="premium",
                            filters={"mode": "family"})
        virt = gen._family_virtual_member()
        assert "орех" in virt["hard_exclude"]
        assert "молоко" in virt["hard_exclude"]

    def test_avg_calorie_target(self, family_with_three):
        family, members = family_with_three
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="premium",
                            filters={"mode": "family"})
        virt = gen._family_virtual_member()
        # head=2400, wife=2000, kid=1500 → avg = 1966
        assert virt["calorie_target"] == int((2400 + 2000 + 1500) / 3)

    def test_no_calorie_target_when_no_profile_data(self, family_with_three):
        family, members = family_with_three
        # Снести calorie_target всем
        for m in members:
            m.user.profile.calorie_target = None
            m.user.profile.save()
        gen = MenuGenerator(family=family, members=members, period_days=1,
                            start_date=datetime.date.today(), plan_code="premium",
                            filters={"mode": "family"})
        virt = gen._family_virtual_member()
        assert virt["calorie_target"] is None


# ─────────────────────────── e2e: HTTP /menu/generate ─────────────────────────

@pytest.mark.django_db
class TestModeAPI:
    def test_generate_default_mode_family(self, client, family_with_three):
        family, members = family_with_three
        client.force_authenticate(family.owner)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1},
            format="json",
        )
        assert resp.status_code == 201
        menu_id = resp.data["id"]
        # default mode → в filters_used должен быть "family"
        menu = Menu.objects.get(id=menu_id)
        assert menu.filters_used.get("mode") == "family"

    def test_generate_explicit_per_member(self, client, family_with_three):
        family, members = family_with_three
        client.force_authenticate(family.owner)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "mode": "per_member"},
            format="json",
        )
        assert resp.status_code == 201
        menu = Menu.objects.get(id=resp.data["id"])
        assert menu.filters_used.get("mode") == "per_member"

    def test_invalid_mode_400(self, client, family_with_three):
        family, _ = family_with_three
        client.force_authenticate(family.owner)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "mode": "weird"},
            format="json",
        )
        assert resp.status_code == 400

    def test_family_mode_creates_items_for_each_member(self, client, family_with_three):
        family, members = family_with_three
        client.force_authenticate(family.owner)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "mode": "family"},
            format="json",
        )
        assert resp.status_code == 201

        # В БД должны быть MenuItem для всех 3 членов
        member_ids_in_db = set(
            MenuItem.objects.filter(menu_id=resp.data["id"], is_cheat_meal=False)
            .values_list("member_id", flat=True)
        )
        expected = {m.id for m in members}
        assert expected.issubset(member_ids_in_db)
PYEOF

echo "  $TEST создан"
echo

echo "[2] py_compile нового файла"
$COMPOSE exec -T backend python -m py_compile apps/menu/tests/test_mg_605a_mode.py && echo "  OK"
echo

echo "[3] Прогон test_mg_605a_mode.py"
$COMPOSE exec -T backend pytest apps/menu/tests/test_mg_605a_mode.py -v --tb=short 2>&1 | tail -50
echo

echo "[4] Регрессионный прогон всего apps/menu + apps/recipes"
$COMPOSE exec -T backend pytest apps/menu/ apps/recipes/ -q --tb=short 2>&1 | tail -15
echo

echo "=== 605.A tests done ==="
