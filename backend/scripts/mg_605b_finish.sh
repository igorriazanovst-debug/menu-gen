#!/usr/bin/env bash
# MG-605.B finish: OneToOne для planned_menu_item + тесты
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
DIARY="$BACKEND/apps/diary"

# ─────────────────────────────────────────────────────────────────────────────
# [1] Заменить ForeignKey(unique=True) → OneToOneField
# ─────────────────────────────────────────────────────────────────────────────
echo "[1] models.py: ForeignKey(unique=True) → OneToOneField"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/models.py")
src = p.read_text(encoding="utf-8")

old = (
    '    # MG_605B_V_models: план-факт\n'
    '    planned_menu_item = models.ForeignKey(\n'
    '        MenuItem,\n'
    '        on_delete=models.SET_NULL,\n'
    '        null=True,\n'
    '        blank=True,\n'
    '        unique=True,\n'
    '        related_name="diary_entries",\n'
    '    )\n'
)
new = (
    '    # MG_605B_V_models: план-факт (OneToOne — один план → один факт)\n'
    '    planned_menu_item = models.OneToOneField(\n'
    '        MenuItem,\n'
    '        on_delete=models.SET_NULL,\n'
    '        null=True,\n'
    '        blank=True,\n'
    '        related_name="diary_entry",\n'
    '    )\n'
)
assert old in src, "ОШИБКА: не нашёл блок planned_menu_item"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("  models.py: пропатчен")
PYEOF

echo
echo "[2] makemigrations diary (новая миграция 0005)"
$COMPOSE exec -T backend python manage.py makemigrations diary --name planned_menu_item_o2o 2>&1 | tail -8
echo

echo "  Содержимое новой миграции:"
$COMPOSE exec -T backend bash -c 'cat apps/diary/migrations/0005*.py 2>/dev/null'
echo

echo "[3] migrate diary"
$COMPOSE exec -T backend python manage.py migrate diary 2>&1 | tail -8
echo

echo "[4] django check (без W342)"
$COMPOSE exec -T backend python manage.py check 2>&1 | tail -5
echo

# ─────────────────────────────────────────────────────────────────────────────
# [5] Тесты MG-605.B
# ─────────────────────────────────────────────────────────────────────────────
echo "[5] Создаю тесты test_mg_605b_planned_eaten.py"

TEST="$DIARY/tests/test_mg_605b_planned_eaten.py"
cat > "$TEST" <<'PYEOF'
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
PYEOF

echo "  $TEST создан"
echo

echo "[6] py_compile + прогон новых тестов"
$COMPOSE exec -T backend python -m py_compile apps/diary/tests/test_mg_605b_planned_eaten.py && echo "  OK"
echo

echo "[7] pytest apps/diary/tests/test_mg_605b_planned_eaten.py -v"
$COMPOSE exec -T backend pytest apps/diary/tests/test_mg_605b_planned_eaten.py -v --tb=short 2>&1 | tail -25
echo

echo "[8] Полный регресс apps/diary"
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=short 2>&1 | tail -10
echo

echo "=== 605.B finish done ==="
