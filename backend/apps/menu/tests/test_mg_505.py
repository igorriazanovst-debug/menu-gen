"""
MG-505 tests: cheat-meal слот.

Сценарии:
  1. _mg505_is_cheat_day: last=None → False
  2. _mg505_is_cheat_day: interval достигнут → True
  3. _mg505_is_cheat_day: interval не достигнут → False
  4. _mg505_is_cheat_day: interval=0 → False (выключено)
  5. _mg505_is_cheat_day: profile отсутствует → False (member без user / user без profile)
  6. _mg505_pick_cheat_slot: детерминированный выбор lunch/dinner
  7. _mg505_mark_cheat_meal_used: обновляет profile.last_cheat_meal_date
  8. _mg505_mark_cheat_meal_used: без профиля — не падает
  9. _pick_for_role(is_cheat=True) — bypass MG-302 для protein (red_meat сверх лимита)
 10. _pick_for_role(is_cheat=True) — bypass MG-303 (любые калории)

# MG_505_V_tests
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model

from apps.menu.generator import (
    CHEAT_MEAL_DEFAULT_INTERVAL,
    CHEAT_MEAL_SLOTS,
    MenuGenerator,
    _mg505_is_cheat_day,
    _mg505_mark_cheat_meal_used,
    _mg505_pick_cheat_slot,
    RED_MEAT_MAX_GRAMS_PER_WEEK,
)
from apps.users.models import Profile

User = get_user_model()
pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Фикстуры
# --------------------------------------------------------------------------

@pytest.fixture
def user_with_profile():
    u = User.objects.create(name="MG505 User", email="mg505@test.local")
    u.set_password("xx")
    u.save()
    p = Profile.objects.create(
        user=u,
        birth_year=1990,
        gender=Profile.Gender.MALE,
        height_cm=180,
        weight_kg=Decimal("75"),
        activity_level=Profile.ActivityLevel.MODERATE,
        goal=Profile.Goal.MAINTAIN,
    )
    return u, p


def _make_member(user=None, member_id=1):
    """Лёгкий объект-член семьи (без БД) для unit-тестов."""
    m = MagicMock()
    m.id = member_id
    m.user = user
    return m


# --------------------------------------------------------------------------
# 1-5: _mg505_is_cheat_day
# --------------------------------------------------------------------------

def test_is_cheat_day_first_time_returns_false(user_with_profile):
    """last_cheat_meal_date=None → False (отсчёт от сегодня)."""
    u, p = user_with_profile
    p.cheat_meal_interval = 10
    p.last_cheat_meal_date = None
    p.save()
    member = _make_member(user=u)
    assert _mg505_is_cheat_day(member, date.today()) is False


def test_is_cheat_day_interval_reached(user_with_profile):
    """last=today-10, interval=10 → True."""
    u, p = user_with_profile
    today = date.today()
    p.cheat_meal_interval = 10
    p.last_cheat_meal_date = today - timedelta(days=10)
    p.save()
    member = _make_member(user=u)
    assert _mg505_is_cheat_day(member, today) is True


def test_is_cheat_day_under_interval(user_with_profile):
    """last=today-9, interval=10 → False."""
    u, p = user_with_profile
    today = date.today()
    p.cheat_meal_interval = 10
    p.last_cheat_meal_date = today - timedelta(days=9)
    p.save()
    member = _make_member(user=u)
    assert _mg505_is_cheat_day(member, today) is False


def test_is_cheat_day_zero_interval(user_with_profile):
    """interval=0 → выключено → False."""
    u, p = user_with_profile
    p.cheat_meal_interval = 0
    p.last_cheat_meal_date = date.today() - timedelta(days=100)
    p.save()
    member = _make_member(user=u)
    assert _mg505_is_cheat_day(member, date.today()) is False


def test_is_cheat_day_no_profile_returns_false():
    """member без user → False (без падения)."""
    member = _make_member(user=None)
    assert _mg505_is_cheat_day(member, date.today()) is False


# --------------------------------------------------------------------------
# 6: _mg505_pick_cheat_slot
# --------------------------------------------------------------------------

def test_pick_cheat_slot_deterministic():
    """Чередование lunch/dinner по (member_id + day_offset) % 2."""
    assert _mg505_pick_cheat_slot(0, 0) == CHEAT_MEAL_SLOTS[0]  # lunch
    assert _mg505_pick_cheat_slot(0, 1) == CHEAT_MEAL_SLOTS[1]  # dinner
    assert _mg505_pick_cheat_slot(1, 0) == CHEAT_MEAL_SLOTS[1]  # dinner
    assert _mg505_pick_cheat_slot(1, 1) == CHEAT_MEAL_SLOTS[0]  # lunch
    assert _mg505_pick_cheat_slot(7, 3) == CHEAT_MEAL_SLOTS[(7 + 3) % 2]


def test_cheat_meal_default_interval_is_10():
    assert CHEAT_MEAL_DEFAULT_INTERVAL == 10


def test_cheat_meal_slots_are_lunch_or_dinner():
    assert set(CHEAT_MEAL_SLOTS) == {"lunch", "dinner"}


# --------------------------------------------------------------------------
# 7-8: _mg505_mark_cheat_meal_used
# --------------------------------------------------------------------------

def test_mark_cheat_meal_used_updates_profile_date(user_with_profile):
    u, p = user_with_profile
    target = date.today() - timedelta(days=2)
    member = _make_member(user=u)

    _mg505_mark_cheat_meal_used(member, target)

    p.refresh_from_db()
    assert p.last_cheat_meal_date == target


def test_mark_cheat_meal_used_no_profile_safe():
    """member без user — не падает."""
    member = _make_member(user=None)
    _mg505_mark_cheat_meal_used(member, date.today())  # не должно быть Exception


# --------------------------------------------------------------------------
# 9-10: _pick_for_role(is_cheat=True) — bypass правил
# --------------------------------------------------------------------------

def _make_recipe(rid, food_group="protein", calories=500.0,
                 is_red_meat=False, is_fatty_fish=False, has_added_sugar=False,
                 protein_type=None, oil_tsp=0.0):
    """Фабрика mock-рецепта."""
    r = MagicMock(spec=["id", "food_group", "nutrition", "is_red_meat",
                        "is_fatty_fish", "has_added_sugar", "protein_type",
                        "ingredients", "suitable_for", "name"])
    r.id = rid
    r.food_group = food_group
    r.nutrition = {"calories": {"value": calories}, "oil_tsp": oil_tsp}
    r.is_red_meat = is_red_meat
    r.is_fatty_fish = is_fatty_fish
    r.has_added_sugar = has_added_sugar
    r.protein_type = protein_type
    r.ingredients = []
    r.suitable_for = ["breakfast", "lunch", "dinner", "snack"]
    r.name = f"recipe_{rid}"
    return r


def _make_generator():
    """Минимальный MenuGenerator для вызова _pick_for_role."""
    family = MagicMock()
    family.id = 1
    members = [_make_member(user=None, member_id=1)]
    g = MenuGenerator(
        family=family,
        members=members,
        period_days=1,
        start_date=date.today(),
        plan_code="free",
        filters={},
    )
    return g


def test_pick_for_role_cheat_bypasses_calorie_filter():
    """is_cheat=True: target_cal задан, но рецепт с любыми калориями допускается."""
    g = _make_generator()
    # один рецепт с калориями ОЧЕНЬ далеко от target
    r = _make_recipe(1, food_group="protein", calories=2000.0)
    pools = {"protein": [r]}

    picked = g._pick_for_role(
        role="protein",
        meal_type="lunch",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=300.0,    # 2000 далеко от 300 — без cheat был бы отфильтрован
        member_id=1,
        day_offset=0,
        is_cheat=True,
    )
    assert picked is not None
    assert picked.id == 1


def test_pick_for_role_cheat_bypasses_red_meat_limit():
    """is_cheat=True: даже при превышении 500г red_meat рецепт red_meat выбирается."""
    g = _make_generator()
    # эмулируем что в этой неделе уже >500г red_meat
    g.tracker.get_week(1, 0)["red_meat_grams"] = 600.0

    red = _make_recipe(1, food_group="protein", calories=500.0,
                       is_red_meat=True, protein_type="animal")
    pools = {"protein": [red]}

    picked = g._pick_for_role(
        role="protein",
        meal_type="lunch",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=None,
        member_id=1,
        day_offset=0,
        is_cheat=True,
    )
    assert picked is not None
    assert picked.is_red_meat is True


def test_pick_for_role_normal_blocks_red_meat_overlimit():
    """is_cheat=False (по умолчанию): red_meat блокируется при превышении лимита."""
    g = _make_generator()
    g.tracker.get_week(1, 0)["red_meat_grams"] = RED_MEAT_MAX_GRAMS_PER_WEEK + 100.0

    red = _make_recipe(1, food_group="protein", calories=500.0,
                       is_red_meat=True, protein_type="animal")
    plant = _make_recipe(2, food_group="protein", calories=500.0,
                         protein_type="plant")
    pools = {"protein": [red, plant]}

    picked = g._pick_for_role(
        role="protein",
        meal_type="lunch",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=None,
        member_id=1,
        day_offset=0,
        # is_cheat=False по умолчанию
    )
    assert picked is not None
    # должен быть выбран не-red_meat вариант (есть альтернатива)
    assert picked.is_red_meat is False
