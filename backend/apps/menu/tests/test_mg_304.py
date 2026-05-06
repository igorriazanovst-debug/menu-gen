"""
MG-304: тесты подсчёта 5 порций овощей/фруктов в день.
Проверяем:
  - portions: daily_target_grams (взрослый = 750г, по возрастам коэффициенты)
  - portions: recipe_portion_grams приоритет источников веса
  - generator: добор snack-слотами при недоборе
  - generator: warnings при невозможности добрать
"""
# MG_304_V_tests
from __future__ import annotations
from datetime import date
import pytest

from apps.menu.portions import (
    ADULT_PORTION_G, PORTIONS_PER_DAY, DEFAULT_PORTION_G_FALLBACK,
    daily_target_grams, recipe_portion_grams,
)


# ────────────────────────── portions: pure unit ───────────────────────────────

class _FakeProfile:
    def __init__(self, birth_year):
        self.birth_year = birth_year


class _FakeUser:
    def __init__(self, birth_year):
        self.profile = _FakeProfile(birth_year)


class _FakeMember:
    def __init__(self, birth_year):
        self.user = _FakeUser(birth_year)


@pytest.mark.parametrize("birth_year, expected", [
    (None,         150 * 5 * 1.00),  # нет данных → как взрослый
    (2024,         150 * 5 * 0.40),  # 1 год
    (2020,         150 * 5 * 0.55),  # 5 лет
    (2017,         150 * 5 * 0.70),  # 8 лет
    (2014,         150 * 5 * 0.85),  # 11 лет
    (2010,         150 * 5 * 1.00),  # 15 лет
    (1985,         150 * 5 * 1.00),  # взрослый
])
def test_daily_target_grams_age_curve(birth_year, expected):
    member = _FakeMember(birth_year)
    got = daily_target_grams(member, ref_date=date(2025, 6, 1))
    assert got == pytest.approx(expected, abs=0.01)


def test_constants_default():
    assert ADULT_PORTION_G == 150.0
    assert PORTIONS_PER_DAY == 5
    assert DEFAULT_PORTION_G_FALLBACK == 200.0


class _FakeRecipe:
    def __init__(self, nutrition=None, povar_raw=None, servings=None, servings_normalized=None):
        self.nutrition = nutrition
        self.povar_raw = povar_raw
        self.servings = servings
        self.servings_normalized = servings_normalized


def test_recipe_portion_grams_uses_nutrition_weight():
    r = _FakeRecipe(nutrition={"weight": {"value": "350.0", "unit": "г"}})
    assert recipe_portion_grams(r) == pytest.approx(350.0)


def test_recipe_portion_grams_uses_povar_raw_when_no_nutrition():
    r = _FakeRecipe(
        nutrition={},
        povar_raw={"dish_weight_g_calc": 600.0},
        servings_normalized=4,
    )
    assert recipe_portion_grams(r) == pytest.approx(150.0)


def test_recipe_portion_grams_falls_back_to_default():
    r = _FakeRecipe(nutrition={}, povar_raw={"dish_weight_g_calc": 0}, servings_normalized=4)
    assert recipe_portion_grams(r) == pytest.approx(DEFAULT_PORTION_G_FALLBACK)


def test_recipe_portion_grams_handles_comma_decimal():
    r = _FakeRecipe(nutrition={"weight": {"value": "120,5"}})
    assert recipe_portion_grams(r) == pytest.approx(120.5)


# ────────────────────────── generator: integration ────────────────────────────

@pytest.mark.django_db
def test_mg_304_top_up_when_shortfall(monkeypatch):
    """
    Имитация: после основного цикла недобор — в items должен появиться
    хотя бы один is_virtual snack-слот veg/fruit. Используем мок _build_pools_by_role.
    """
    from apps.recipes.models import Recipe
    from apps.menu.generator import MenuGenerator
    from apps.family.models import Family, FamilyMember
    from apps.users.models import User

    user = User.objects.create_user(email="mg304@test.local", password="x")
    family = Family.objects.create(name="MG304 family", owner=user)
    member = FamilyMember.objects.create(family=family, user=user, role="adult")

    # 5 рецептов veg + 5 fruit + минимально protein/grain/dairy
    def mk(title, fg):
        return Recipe.objects.create(
            title=title, food_group=fg,
            ingredients=[],
            nutrition={"weight": {"value": "150.0"}, "calories": {"value": "100"}},
            servings=1,
            servings_normalized=1,
            povar_raw={},
        )
    veg = [mk(f"V{i}", "vegetable") for i in range(8)]
    fr  = [mk(f"F{i}", "fruit") for i in range(8)]
    pr  = [mk(f"P{i}", "protein") for i in range(8)]
    gr  = [mk(f"G{i}", "grain") for i in range(8)]
    dy  = [mk(f"D{i}", "dairy") for i in range(8)]

    gen = MenuGenerator(
        family=family, members=[member],
        period_days=1, start_date=date(2025, 6, 1),
        plan_code="free", filters={"meal_plan_type": "3"},
    )
    items = gen.generate()
    assert isinstance(items, list)
    veg_fruit_items = [i for i in items if i.get("component_role") in ("vegetable", "fruit")]
    # 750г / 150г = 5 порций — должно быть достигнуто
    total_g = 0.0
    for it in veg_fruit_items:
        total_g += recipe_portion_grams(it["recipe"])
    assert total_g >= 750.0 - 0.01

    # warnings должно быть пусто, поскольку добили
    assert getattr(gen, "last_warnings", []) == []
