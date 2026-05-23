"""
MG-302: недельные/дневные лимиты в генераторе меню.
  - red_meat   ≤ 500 г/нед
  - fatty_fish ≥ 2  раз/нед (boost)
  - plant      ≥ 1  раз/день (boost)

Политика: soft+warnings. Генератор не падает, нарушения — в last_warnings.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from apps.menu import generator as gen_module
from apps.menu.generator import FATTY_FISH_MIN_PER_WEEK, RED_MEAT_MAX_GRAMS_PER_WEEK, MenuGenerator, _WeeklyTracker

# ───── _WeeklyTracker unit tests ─────────────────────────────────────────────


class _R:
    """Лёгкий «рецепт» для трекера."""

    def __init__(
        self,
        rid=1,
        is_red_meat=False,
        is_fatty_fish=False,
        protein_type=None,
        portion_g=200.0,
        food_group=None,
        nutrition=None,
        ingredients=None,
        suitable_for=None,
        is_published=True,
        country=None,
        cook_time=None,
    ):
        self.id = rid
        self.is_red_meat = is_red_meat
        self.is_fatty_fish = is_fatty_fish
        self.protein_type = protein_type
        self._portion_g = portion_g
        self.food_group = food_group
        self.nutrition = nutrition or {}
        self.ingredients = ingredients or []
        self.suitable_for = suitable_for
        self.is_published = is_published
        self.country = country
        self.cook_time = cook_time


def _fake_portion_grams_factory(by_id):
    def _fake(recipe):
        return by_id.get(recipe.id, getattr(recipe, "_portion_g", 200.0))

    return _fake


def test_tracker_red_meat_grams_accumulate():
    t = _WeeklyTracker()
    r = _R(rid=1, is_red_meat=True, portion_g=300.0)
    with patch.object(gen_module, "recipe_portion_grams", side_effect=_fake_portion_grams_factory({1: 300.0})):
        t.add(member_id=10, day_offset=0, recipe=r)
        t.add(member_id=10, day_offset=3, recipe=r)
    assert t.get_week(10, 0)["red_meat_grams"] == 600.0
    # другая неделя — отдельный счётчик
    assert t.get_week(10, 8)["red_meat_grams"] == 0.0


def test_tracker_fatty_fish_per_week_count():
    t = _WeeklyTracker()
    fish = _R(rid=2, is_fatty_fish=True)
    with patch.object(gen_module, "recipe_portion_grams", return_value=150.0):
        t.add(11, 0, fish)
        t.add(11, 2, fish)
    assert t.get_week(11, 0)["fatty_fish"] == 2


def test_tracker_plant_per_day_count():
    t = _WeeklyTracker()
    pl = _R(rid=3, protein_type="plant")
    an = _R(rid=4, protein_type="animal")
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        t.add(12, 0, pl)
        t.add(12, 0, an)
        t.add(12, 1, an)
    assert t.get_day(12, 0)["plant"] == 1
    assert t.get_day(12, 0)["animal"] == 1
    assert t.get_day(12, 1)["plant"] == 0


# ───── _pick_for_role: правила приоритета ────────────────────────────────────


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


def _make_gen(members=None, period=7):
    class _Fam:
        id = 1

    return MenuGenerator(
        family=_Fam(),
        members=members or [_Member()],
        period_days=period,
        start_date=date(2026, 1, 5),
        plan_code="free",
        filters={},
    )


def test_pick_red_meat_blocked_after_500g():
    g = _make_gen()
    # уже набрано 500г красного мяса в неделе 0
    g.tracker.get_week(1, 0)["red_meat_grams"] = 500.0

    red = _R(rid=100, is_red_meat=True, food_group="protein")
    other = _R(rid=101, is_red_meat=False, food_group="protein", protein_type="animal")

    pools = {"main": [red, other], "grain": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        # plant за день уже есть — чтобы не сработал plant-boost
        g.tracker.get_day(1, 0)["plant"] = 1
        # fish boost: считаем выполненным
        g.tracker.get_week(1, 0)["fatty_fish"] = FATTY_FISH_MIN_PER_WEEK
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="main",
                meal_type="lunch",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 101  # red был отрезан


def test_pick_red_meat_fallback_when_no_alternative():
    """Если в candidates только red_meat — отдаём его (не падаем)."""
    g = _make_gen()
    g.tracker.get_week(1, 0)["red_meat_grams"] = 500.0
    red = _R(rid=200, is_red_meat=True, food_group="protein", protein_type="animal")
    pools = {"main": [red], "grain": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}
    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        g.tracker.get_day(1, 0)["plant"] = 1
        g.tracker.get_week(1, 0)["fatty_fish"] = FATTY_FISH_MIN_PER_WEEK
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="main",
                meal_type="lunch",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked is not None and picked.id == 200


def test_pick_plant_boost_when_zero_for_day():
    g = _make_gen()
    plant = _R(rid=300, protein_type="plant", food_group="protein")
    animal = _R(rid=301, protein_type="animal", food_group="protein")
    pools = {"main": [plant, animal], "grain": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        # plant=0, fish=0 — должен сработать plant boost (приоритетней)
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="main",
                meal_type="lunch",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 300


def test_pick_fish_boost_when_plant_already_done():
    g = _make_gen()
    fish = _R(rid=400, is_fatty_fish=True, protein_type="animal", food_group="protein")
    other = _R(rid=401, protein_type="animal", food_group="protein")
    pools = {"main": [fish, other], "grain": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}
    with patch.object(gen_module, "recipe_portion_grams", return_value=180.0):
        g.tracker.get_day(1, 0)["plant"] = 1  # plant уже сделан
        # fish=0 — должен сработать fish boost
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="main",
                meal_type="lunch",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 400


def test_pick_no_boost_when_all_satisfied():
    """plant уже есть, fish ≥ норма, red_meat в норме — обычная случайная выборка."""
    g = _make_gen()
    a = _R(rid=500, protein_type="animal", food_group="protein")
    b = _R(rid=501, protein_type="animal", food_group="protein")
    pools = {"main": [a, b], "grain": [], "vegetable": [], "fruit": [], "dairy": [], "oil": [], "other": []}
    with patch.object(gen_module, "recipe_portion_grams", return_value=180.0):
        g.tracker.get_day(1, 0)["plant"] = 1
        g.tracker.get_week(1, 0)["fatty_fish"] = FATTY_FISH_MIN_PER_WEEK
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="main",
                meal_type="lunch",
                pools=pools,
                used=set(),
                hard_exclude=set(),
                fridge_ids=set(),
                target_cal=None,
                member_id=1,
                day_offset=0,
            )
    assert picked.id == 500  # candidates не сужались


# ───── warnings collectors ───────────────────────────────────────────────────


def test_collect_weekly_warnings_red_meat_overlimit():
    g = _make_gen(period=7)
    g.tracker.get_week(g.members[0].id, 0)["red_meat_grams"] = 750.0
    g.tracker.get_week(g.members[0].id, 0)["fatty_fish"] = FATTY_FISH_MIN_PER_WEEK
    out = g._collect_weekly_warnings()
    codes = [w["code"] for w in out]
    assert "red_meat_overlimit" in codes
    rm = next(w for w in out if w["code"] == "red_meat_overlimit")
    assert rm["actual_grams"] == 750.0
    assert rm["limit_grams"] == RED_MEAT_MAX_GRAMS_PER_WEEK


def test_collect_weekly_warnings_fish_shortfall():
    g = _make_gen(period=7)
    g.tracker.get_week(g.members[0].id, 0)["fatty_fish"] = 1
    g.tracker.get_week(g.members[0].id, 0)["red_meat_grams"] = 0.0
    out = g._collect_weekly_warnings()
    codes = [w["code"] for w in out]
    assert "fatty_fish_shortfall" in codes


def test_collect_daily_plant_warnings():
    g = _make_gen(period=3)
    # день 0: plant=0 → warning; день 1: plant=1 → нет; день 2: plant=0 → warning
    g.tracker.get_day(g.members[0].id, 1)["plant"] = 1
    out = g._collect_daily_plant_warnings()
    days = sorted(w["day_offset"] for w in out if w["code"] == "plant_protein_shortfall")
    assert days == [0, 2]
