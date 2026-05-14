"""
MG-303 tests: распределение КБЖУ по приёмам.

Проверяем:
  1) MEAL_CALORIE_WEIGHTS_3 / _5 — суммы и наличие всех слотов
  2) _meal_target_cal — корректные веса для 3- и 5-плана
  3) _pick_for_role — эскалация окна ±15/30/50% (по mock-пулу с известными калориями)
  4) _collect_meal_calorie_warnings — пишет meal_calorie_mismatch при отклонении >50%
"""

# MG_303_V_tests
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from apps.menu import generator as g


# ── 1. Константы весов ────────────────────────────────────────────────────
def test_mg_303_weights_3_sum_to_1():
    s = sum(g.MEAL_CALORIE_WEIGHTS_3.values())
    assert abs(s - 1.0) < 1e-9, f"weights 3 sum={s}"
    assert set(g.MEAL_CALORIE_WEIGHTS_3.keys()) == {"breakfast", "lunch", "dinner"}


def test_mg_303_weights_5_sum_to_1():
    s = sum(g.MEAL_CALORIE_WEIGHTS_5.values())
    assert abs(s - 1.0) < 1e-9, f"weights 5 sum={s}"
    assert set(g.MEAL_CALORIE_WEIGHTS_5.keys()) == {
        "breakfast",
        "snack1",
        "lunch",
        "snack2",
        "dinner",
    }


def test_mg_303_window_tiers_ordered():
    assert g.MEAL_CAL_WINDOW_TIERS == (0.15, 0.30, 0.50)


# ── helpers для построения генератора без БД ─────────────────────────────
def _make_gen(meal_plan_type="3"):
    family = MagicMock(id=1)
    member = MagicMock(id=10)
    member.user = MagicMock()
    member.user.profile = MagicMock(calorie_target=2000)
    gen = g.MenuGenerator.__new__(g.MenuGenerator)
    gen.family = family
    gen.members = [member]
    gen.period_days = 1
    gen.start_date = date(2026, 5, 8)
    gen.plan_code = "premium"
    gen.features = g.TIER_FEATURES["premium"]
    gen.filters = {"meal_plan_type": meal_plan_type}
    gen.meal_types = g.MEAL_PLAN_5 if meal_plan_type == "5" else g.MEAL_PLAN_3
    gen.tracker = g._WeeklyTracker()
    gen.last_warnings = []
    from collections import defaultdict

    gen._meal_cal_actual = defaultdict(float)
    gen._meal_cal_target = {}
    return gen


# ── 2. _meal_target_cal ──────────────────────────────────────────────────
def test_mg_303_meal_target_cal_3plan():
    gen = _make_gen("3")
    assert gen._meal_target_cal(2000, "breakfast") == pytest.approx(500.0)  # 0.25
    assert gen._meal_target_cal(2000, "lunch") == pytest.approx(800.0)  # 0.40
    assert gen._meal_target_cal(2000, "dinner") == pytest.approx(700.0)  # 0.35


def test_mg_303_meal_target_cal_5plan():
    gen = _make_gen("5")
    assert gen._meal_target_cal(2000, "breakfast") == pytest.approx(600.0)  # 0.30
    assert gen._meal_target_cal(2000, "snack1") == pytest.approx(100.0)  # 0.05
    assert gen._meal_target_cal(2000, "lunch") == pytest.approx(700.0)  # 0.35
    assert gen._meal_target_cal(2000, "snack2") == pytest.approx(100.0)  # 0.05
    assert gen._meal_target_cal(2000, "dinner") == pytest.approx(500.0)  # 0.25


def test_mg_303_meal_target_cal_no_target():
    gen = _make_gen("3")
    assert gen._meal_target_cal(None, "breakfast") is None
    assert gen._meal_target_cal(0, "breakfast") is None


def test_mg_303_meal_target_cal_unknown_slot_fallback():
    gen = _make_gen("3")
    # неизвестный slot → равные доли 2000/3
    assert gen._meal_target_cal(2000, "supper") == pytest.approx(2000.0 / 3.0)


# ── 3. _pick_for_role: эскалация окна ────────────────────────────────────
def _r(rid: int, cal: float, food_group="grain", protein_type=None, is_red_meat=False, is_fatty_fish=False):
    """Build a mock recipe."""
    r = MagicMock()
    r.id = rid
    r.food_group = food_group
    r.protein_type = protein_type
    r.is_red_meat = is_red_meat
    r.is_fatty_fish = is_fatty_fish
    r.suitable_for = None
    r.ingredients = []
    r.nutrition = {"calories": {"value": cal}}
    return r


def test_mg_303_pick_for_role_picks_inside_15pct():
    """target=500, есть рецепты в ±15% (425..575) и за окном — выбираем из ±15%."""
    gen = _make_gen("3")
    pool = [
        _r(1, 500.0, "grain"),  # exact match
        _r(2, 450.0, "grain"),  # в 15%
        _r(3, 800.0, "grain"),  # вне 15%
    ]
    pools = {"grain": pool}
    chosen = gen._pick_for_role(
        role="grain",
        meal_type="breakfast",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=500.0,
        member_id=10,
        day_offset=0,
    )
    assert chosen is not None
    assert chosen.id in (1, 2)


def test_mg_303_pick_for_role_escalates_to_30pct():
    """target=500, в ±15% пусто, в ±30% есть — выбираем из ±30%."""
    gen = _make_gen("3")
    pool = [
        _r(1, 600.0, "grain"),  # 600 = +20% — в 30%, не в 15%
        _r(2, 900.0, "grain"),  # вне 50%
    ]
    pools = {"grain": pool}
    chosen = gen._pick_for_role(
        role="grain",
        meal_type="breakfast",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=500.0,
        member_id=10,
        day_offset=0,
    )
    assert chosen.id == 1


def test_mg_303_pick_for_role_escalates_to_50pct():
    """target=500, попадает только в ±50%."""
    gen = _make_gen("3")
    pool = [
        _r(1, 700.0, "grain"),  # +40% — в 50%, не в 30%
        _r(2, 1200.0, "grain"),  # вне 50%
    ]
    pools = {"grain": pool}
    chosen = gen._pick_for_role(
        role="grain",
        meal_type="breakfast",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=500.0,
        member_id=10,
        day_offset=0,
    )
    assert chosen.id == 1


def test_mg_303_pick_for_role_fallback_random_outside_50pct():
    """Никто не попадает в ±50% — выбираем как есть (random из всех candidates)."""
    gen = _make_gen("3")
    pool = [
        _r(1, 1500.0, "grain"),  # +200%
        _r(2, 100.0, "grain"),  # -80%
    ]
    pools = {"grain": pool}
    chosen = gen._pick_for_role(
        role="grain",
        meal_type="breakfast",
        pools=pools,
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=500.0,
        member_id=10,
        day_offset=0,
    )
    assert chosen is not None  # выбор сделан, не None


# ── 4. _collect_meal_calorie_warnings ────────────────────────────────────
def test_mg_303_collect_warnings_writes_mismatch_over_50pct():
    gen = _make_gen("3")
    # target 500, actual 800 → delta +60% → warning
    gen._meal_cal_target[(10, 0, "breakfast")] = 500.0
    gen._meal_cal_actual[(10, 0, "breakfast")] = 800.0
    out = gen._collect_meal_calorie_warnings()
    assert len(out) == 1
    w = out[0]
    assert w["code"] == "meal_calorie_mismatch"
    assert w["member_id"] == 10
    assert w["day_offset"] == 0
    assert w["meal_slot"] == "breakfast"
    assert w["target_cal"] == 500.0
    assert w["actual_cal"] == 800.0
    assert w["delta_cal"] == 300.0
    assert w["delta_pct"] == 60.0


def test_mg_303_collect_warnings_silent_inside_50pct():
    gen = _make_gen("3")
    # target 500, actual 700 → delta +40% → нет warning
    gen._meal_cal_target[(10, 0, "lunch")] = 500.0
    gen._meal_cal_actual[(10, 0, "lunch")] = 700.0
    out = gen._collect_meal_calorie_warnings()
    assert out == []


def test_mg_303_collect_warnings_skips_no_target():
    gen = _make_gen("3")
    gen._meal_cal_target[(10, 0, "breakfast")] = None
    gen._meal_cal_actual[(10, 0, "breakfast")] = 1000.0
    assert gen._collect_meal_calorie_warnings() == []


def test_mg_303_collect_warnings_skips_no_actual():
    gen = _make_gen("3")
    gen._meal_cal_target[(10, 0, "breakfast")] = 500.0
    # actual не записан (приём не сгенерился — нечего сравнивать)
    assert gen._collect_meal_calorie_warnings() == []
