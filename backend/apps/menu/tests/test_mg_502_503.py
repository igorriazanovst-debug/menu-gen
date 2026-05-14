# MG_502_503_V_tests
"""MG-502 (контроль масла) + MG-503 (исключение сахара) — тесты."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.menu import generator as gen_module
from apps.menu.generator import DAILY_OIL_TSP_LIMIT, MAIN_MEAL_TYPES, SWEET_PER_DAY_LIMIT, MenuGenerator


def _R(
    rid=1,
    oil_tsp=None,
    has_added_sugar=False,
    food_group="grain",
    protein_type=None,
    is_red_meat=False,
    is_fatty_fish=False,
    suitable_for=None,
):
    """Билдер мок-рецепта."""
    r = MagicMock()
    r.id = rid
    r.oil_tsp = Decimal(str(oil_tsp)) if oil_tsp is not None else None
    r.has_added_sugar = has_added_sugar
    r.food_group = food_group
    r.protein_type = protein_type
    r.is_red_meat = is_red_meat
    r.is_fatty_fish = is_fatty_fish
    r.suitable_for = suitable_for or []
    r.nutrition = {}
    r.cook_time = "30 минут"
    r.title = f"recipe_{rid}"
    return r


class _Member:
    def __init__(self, mid=1):
        self.id = mid

        class _U:
            allergies = []
            disliked_products = []
            name = ""
            email = ""

            class profile:
                calorie_target = None

        self.user = _U()


def _make_gen(period=3):
    class _Fam:
        id = 1

    return MenuGenerator(
        family=_Fam(),
        members=[_Member()],
        period_days=period,
        start_date=date(2026, 1, 5),
        plan_code="free",
        filters={},
    )


# ───── tracker.add: oil_tsp / sweet_count ─────────────────────────────────────


def test_tracker_oil_tsp_accumulates_per_day():
    g = _make_gen()
    r1 = _R(rid=1, oil_tsp=1.0)
    r2 = _R(rid=2, oil_tsp=2.5)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, r1)
        g.tracker.add(1, 0, r2)
        g.tracker.add(1, 1, r1)
    assert g.tracker.get_day(1, 0)["oil_tsp"] == pytest.approx(3.5)
    assert g.tracker.get_day(1, 1)["oil_tsp"] == pytest.approx(1.0)
    assert g.tracker.get_day(1, 2)["oil_tsp"] == pytest.approx(0.0)


def test_tracker_oil_tsp_none_means_zero():
    g = _make_gen()
    r = _R(rid=1, oil_tsp=None)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, r)
    assert g.tracker.get_day(1, 0)["oil_tsp"] == pytest.approx(0.0)


def test_tracker_sweet_count_increments():
    g = _make_gen()
    sweet = _R(rid=1, has_added_sugar=True)
    plain = _R(rid=2, has_added_sugar=False)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, sweet)
        g.tracker.add(1, 0, plain)
        g.tracker.add(1, 0, sweet)
    assert g.tracker.get_day(1, 0)["sweet_count"] == 2


# ───── _pick_for_role: MG-502 фильтрация по маслу ─────────────────────────────


def test_pick_oil_filter_when_over_limit():
    """Когда daily oil > 5 ч.л. — режем кандидатов с oil_tsp > 0.5."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 1.0  # уже превышен

    heavy = _R(rid=10, oil_tsp=2.0, food_group="grain")  # маслянистый
    light = _R(rid=11, oil_tsp=0.3, food_group="grain")  # лёгкий
    nones = _R(rid=12, oil_tsp=None, food_group="grain")  # NULL → 0 → лёгкий

    pools = {
        "grain": [heavy, light, nones],
        "protein": [],
        "vegetable": [],
        "fruit": [],
        "dairy": [],
        "oil": [],
        "other": [],
    }

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain",
                meal_type="breakfast",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id in (11, 12), f"должен выбрать light/none, выбран id={picked.id}"


def test_pick_oil_no_filter_under_limit():
    """Под лимитом — фильтр не применяется."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = 2.0  # под лимитом

    heavy = _R(rid=10, oil_tsp=3.0, food_group="grain")
    pools = {"grain": [heavy], "protein": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain",
                meal_type="breakfast",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 10  # heavy не отрезан


def test_pick_oil_fallback_when_only_heavy_available():
    """Превышен, но в пуле только маслянистые → fallback на текущих candidates."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 5.0

    heavy = _R(rid=10, oil_tsp=3.0, food_group="grain")
    pools = {"grain": [heavy], "protein": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain",
                meal_type="breakfast",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked is not None and picked.id == 10


# ───── _pick_for_role: MG-503 исключение сахара ───────────────────────────────


def test_pick_no_sugar_in_main_meals():
    """Для основных приёмов has_added_sugar=True должен быть отрезан."""
    g = _make_gen()

    sweet = _R(rid=20, has_added_sugar=True, food_group="grain")
    plain = _R(rid=21, has_added_sugar=False, food_group="grain")
    pools = {"grain": [sweet, plain], "protein": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}

    for mt in MAIN_MEAL_TYPES:
        with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
            with patch("random.choice", side_effect=lambda c: c[0]):
                picked = g._pick_for_role(
                    role="grain",
                    meal_type=mt,
                    pools=pools,
                    used=set(),
                    hard_exclude=set(),
                    fridge_ids=set(),
                    target_cal=None,
                    member_id=1,
                    day_offset=0,
                )
        assert picked.id == 21, f"в {mt} не должно выбираться сладкое (выбран id={picked.id})"


def test_pick_sugar_allowed_in_snack_first_time():
    """Snack: первый раз сладкое разрешено."""
    g = _make_gen()
    sweet = _R(rid=30, has_added_sugar=True, food_group="fruit")
    pools = {"fruit": [sweet], "grain": [], "protein": [], "vegetable": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="fruit",
                meal_type="snack",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 30


def test_pick_sugar_blocked_in_snack_after_limit():
    """Snack: ≥ SWEET_PER_DAY_LIMIT — режем сладкое."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["sweet_count"] = SWEET_PER_DAY_LIMIT  # уже достигнуто

    sweet = _R(rid=30, has_added_sugar=True, food_group="fruit")
    plain = _R(rid=31, has_added_sugar=False, food_group="fruit")
    pools = {"fruit": [sweet, plain], "grain": [], "protein": [], "vegetable": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="fruit",
                meal_type="snack",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 31  # plain выбран, sweet отрезан


# ───── warnings collectors ───────────────────────────────────────────────────


def test_collect_oil_warnings_above_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 2.0
    g.tracker.get_day(mid, 1)["oil_tsp"] = DAILY_OIL_TSP_LIMIT  # ровно лимит — НЕ warning
    g.tracker.get_day(mid, 2)["oil_tsp"] = 1.0

    out = g._collect_daily_oil_warnings()
    days = sorted(w["day_offset"] for w in out if w["code"] == "oil_overlimit")
    assert days == [0]
    w = next(x for x in out if x["day_offset"] == 0)
    assert w["actual_tsp"] == DAILY_OIL_TSP_LIMIT + 2.0
    assert w["delta_tsp"] == 2.0
    assert w["limit_tsp"] == DAILY_OIL_TSP_LIMIT


def test_collect_oil_warnings_silent_under_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["oil_tsp"] = 2.0
    g.tracker.get_day(mid, 1)["oil_tsp"] = 4.5
    out = g._collect_daily_oil_warnings()
    assert out == []


def test_collect_sweet_warnings_above_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["sweet_count"] = SWEET_PER_DAY_LIMIT + 1  # warning
    g.tracker.get_day(mid, 1)["sweet_count"] = SWEET_PER_DAY_LIMIT  # на грани — НЕ warning
    g.tracker.get_day(mid, 2)["sweet_count"] = 0
    out = g._collect_daily_sweet_warnings()
    days = sorted(w["day_offset"] for w in out if w["code"] == "sweet_overlimit")
    assert days == [0]


def test_collect_sweet_warnings_silent_under_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["sweet_count"] = 0
    g.tracker.get_day(mid, 1)["sweet_count"] = SWEET_PER_DAY_LIMIT
    out = g._collect_daily_sweet_warnings()
    assert out == []
