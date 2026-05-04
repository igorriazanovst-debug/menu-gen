"""
Генератор меню — метод тарелки + недельные ограничения (MG-301, MG-302).

Состав ролей по meal_slot:
  breakfast      -> grain + protein + fruit
  lunch / dinner -> protein + grain + vegetable
  snack1         -> fruit + dairy
  snack2         -> protein + vegetable

Недельные лимиты (per member, скользящее окно 7 дней от start_date):
  - red_meat   ≤ 2 раза/неделю   (мягкий)
  - fatty_fish ≥ 2 раза/неделю   (мягкий бонус)
"""
from __future__ import annotations
import random
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe


MEAL_PLAN_3 = ["breakfast", "lunch", "dinner"]
MEAL_PLAN_5 = ["breakfast", "snack1", "lunch", "snack2", "dinner"]

MEAL_TYPE_DB = {
    "breakfast": "breakfast",
    "lunch":     "lunch",
    "dinner":    "dinner",
    "snack1":    "snack",
    "snack2":    "snack",
}

MEAL_COMPONENTS: Dict[str, Tuple[str, ...]] = {
    "breakfast": ("grain", "protein", "fruit"),
    "lunch":     ("protein", "grain", "vegetable"),
    "dinner":    ("protein", "grain", "vegetable"),
    "snack1":    ("fruit", "dairy"),
    "snack2":    ("protein", "vegetable"),
}

# Недельные лимиты
RED_MEAT_MAX_PER_WEEK   = 2  # не больше
FATTY_FISH_MIN_PER_WEEK = 2  # желательно не меньше

TIER_FEATURES = {
    "free":       {"country": True},
    "lite":       {"country": True, "disliked": True},
    "basic":      {"country": True, "disliked": True, "calories": True},
    "basic_plus": {"country": True, "disliked": True, "calories": True, "fridge": True},
    "premium":    {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
    "horeca":     {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
}


class _WeeklyTracker:
    """Счётчики использований per (member_id, week_index)."""

    def __init__(self):
        # week_index -> member_id -> {"red_meat": int, "fatty_fish": int}
        self._counters: Dict[int, Dict[int, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: {"red_meat": 0, "fatty_fish": 0})
        )

    @staticmethod
    def week_of(day_offset: int) -> int:
        return day_offset // 7

    def get(self, member_id: int, day_offset: int) -> Dict[str, int]:
        return self._counters[self.week_of(day_offset)][member_id]

    def add(self, member_id: int, day_offset: int, recipe: Recipe) -> None:
        c = self.get(member_id, day_offset)
        if getattr(recipe, "is_red_meat", False):
            c["red_meat"] += 1
        if getattr(recipe, "is_fatty_fish", False):
            c["fatty_fish"] += 1


class MenuGenerator:
    """Генератор меню по методу тарелки с учётом недельных ограничений."""

    def __init__(
        self,
        family,
        members,
        period_days: int,
        start_date: date,
        plan_code: str = "free",
        filters: Optional[dict] = None,
    ):
        self.family = family
        self.members = list(members)
        self.period_days = period_days
        self.start_date = start_date
        self.plan_code = plan_code
        self.features = TIER_FEATURES.get(plan_code, TIER_FEATURES["free"])
        self.filters = filters or {}
        meal_count = self.filters.get("meal_plan_type", "3")
        self.meal_types = MEAL_PLAN_5 if str(meal_count) == "5" else MEAL_PLAN_3
        self.tracker = _WeeklyTracker()

    # ── public ────────────────────────────────────────────────────────────────

    def generate(self) -> List[dict]:
        all_recipes = self._build_recipe_pool()
        pools = self._build_pools_by_role(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items: List[dict] = []
        used_per_member: dict = {m.id: set() for m in self.members}

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)

                for meal_slot in self.meal_types:
                    db_meal_type = MEAL_TYPE_DB[meal_slot]
                    roles = MEAL_COMPONENTS.get(meal_slot, ("other",))
                    per_meal_cal = (target_cal / len(self.meal_types)) if target_cal else None
                    per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

                    for role in roles:
                        recipe = self._pick_for_role(
                            role=role,
                            meal_type=db_meal_type,
                            pools=pools,
                            used=used_per_member[member.id],
                            hard_exclude=hard_exclude,
                            fridge_ids=fridge_ids,
                            target_cal=per_role_cal,
                            member_id=member.id,
                            day_offset=day,
                        )
                        if not recipe:
                            continue
                        used_per_member[member.id].add(recipe.id)
                        self.tracker.add(member.id, day, recipe)
                        items.append({
                            "member":         member,
                            "meal_type":      db_meal_type,
                            "meal_slot":      meal_slot,
                            "day_offset":     day,
                            "recipe":         recipe,
                            "component_role": role,
                        })

        return items

    # ── pools ────────────────────────────────────────────────────────────────

    def _build_recipe_pool(self) -> List[Recipe]:
        qs = Recipe.objects.filter(is_published=True)
        country = self.filters.get("country")
        if country and self.features.get("country"):
            qs = qs.filter(country__iexact=country)
        max_time = self.filters.get("max_cook_time")
        recipes = list(qs.order_by("?")[:2000])
        if max_time:
            def _minutes(ct):
                try:
                    return int(str(ct).split()[0])
                except Exception:
                    return 9999
            recipes = [r for r in recipes if _minutes(r.cook_time) <= int(max_time)]
        return recipes

    def _build_pools_by_role(self, recipes: List[Recipe]) -> Dict[str, List[Recipe]]:
        pools: Dict[str, List[Recipe]] = {
            "protein": [], "grain": [], "vegetable": [],
            "fruit": [], "dairy": [], "oil": [], "other": [],
        }
        for r in recipes:
            fg = (getattr(r, "food_group", None) or "other")
            pools.setdefault(fg, []).append(r)
        return pools

    # ── pick ─────────────────────────────────────────────────────────────────

    def _pick_for_role(
        self,
        role: str,
        meal_type: str,
        pools: Dict[str, List[Recipe]],
        used: set,
        hard_exclude: set,
        fridge_ids: set,
        target_cal: Optional[float],
        member_id: int,
        day_offset: int,
    ) -> Optional[Recipe]:
        primary = pools.get(role, [])

        def _ok(r: Recipe, allow_used: bool = False) -> bool:
            if not allow_used and r.id in used:
                return False
            if not self._recipe_passes_hard(r, hard_exclude):
                return False
            sf = getattr(r, "suitable_for", None)
            if sf and meal_type not in sf:
                return False
            return True

        candidates = [r for r in primary if _ok(r)]
        if not candidates:
            candidates = [
                r for r in primary
                if r.id not in used and self._recipe_passes_hard(r, hard_exclude)
            ]
        if not candidates:
            candidates = [r for r in primary if self._recipe_passes_hard(r, hard_exclude)]
        if not candidates and role != "other":
            candidates = [
                r for r in pools.get("other", [])
                if r.id not in used and self._recipe_passes_hard(r, hard_exclude)
            ]
        if not candidates:
            return None

        # Калорийный таргет
        if target_cal:
            cal_ok = [r for r in candidates if (c := self._recipe_cal(r)) and abs(c - target_cal) <= 200]
            if cal_ok:
                candidates = cal_ok

        # Недельные лимиты — применяем только для protein
        if role == "protein":
            counters = self.tracker.get(member_id, day_offset)
            # 1) красное мясо: hard-cap внутри candidates, но с фолбэком
            if counters["red_meat"] >= RED_MEAT_MAX_PER_WEEK:
                no_red = [r for r in candidates if not getattr(r, "is_red_meat", False)]
                if no_red:
                    candidates = no_red
            # 2) жирная рыба: бонус-приоритет, пока счётчик ниже минимума
            if counters["fatty_fish"] < FATTY_FISH_MIN_PER_WEEK:
                fish = [r for r in candidates if getattr(r, "is_fatty_fish", False)]
                if fish:
                    candidates = fish

        # Бонус по холодильнику
        if fridge_ids:
            candidates.sort(key=lambda r: self._fridge_score(r, fridge_ids), reverse=True)
            candidates = candidates[:10]

        return random.choice(candidates)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_fridge_ingredient_names(self) -> set:
        if not self.features.get("fridge"):
            return set()
        items = FridgeItem.objects.filter(family=self.family, is_deleted=False)
        return {i.name.lower() for i in items}

    def _get_hard_exclude(self, member) -> set:
        exclude = set()
        user = member.user
        if isinstance(user.allergies, list):
            exclude.update(a.lower() for a in user.allergies)
        if self.features.get("disliked") and isinstance(user.disliked_products, list):
            exclude.update(d.lower() for d in user.disliked_products)
        if self.features.get("allergies_family"):
            for m in self.members:
                if isinstance(m.user.allergies, list):
                    exclude.update(a.lower() for a in m.user.allergies)
        return exclude

    def _get_calorie_target(self, member) -> Optional[int]:
        if not self.features.get("calories"):
            return None
        try:
            return member.user.profile.calorie_target
        except Exception:
            return None

    def _recipe_passes_hard(self, recipe: Recipe, hard_exclude: set) -> bool:
        if not hard_exclude:
            return True
        for ing in recipe.ingredients:
            name = ing.get("name", "").lower()
            if any(ex in name for ex in hard_exclude):
                return False
        return True

    def _recipe_cal(self, recipe: Recipe) -> Optional[float]:
        try:
            return float(recipe.nutrition.get("calories", {}).get("value", 0))
        except (TypeError, ValueError, AttributeError):
            return None

    def _fridge_score(self, recipe: Recipe, fridge_ids: set) -> int:
        if not fridge_ids:
            return 0
        return sum(1 for ing in recipe.ingredients if ing.get("name", "").lower() in fridge_ids)
