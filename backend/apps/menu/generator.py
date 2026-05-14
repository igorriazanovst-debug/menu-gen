"""
Генератор меню — метод тарелки + недельные/дневные ограничения.

MG-301: жёсткая ошибка при пустом пуле роли + audit
MG-302: недельные ограничения (red_meat ≤500г/нед, fatty_fish ≥2/нед, plant ≥1/день)
MG-303: распределение КБЖУ по приёмам (веса 0.25/0.40/0.35 или 0.30/0.05/0.35/0.05/0.25)
MG-304: 5 порций овощей/фруктов в день (per member)

Состав ролей по meal_slot:
  breakfast      -> grain + protein + fruit
  lunch / dinner -> protein + grain + vegetable
  snack1         -> fruit + dairy
  snack2         -> protein + vegetable

Недельные/дневные лимиты (per member, скользящее окно 7 дней от start_date):
  - red_meat   ≤ 500 г/нед   (мягкий, считается через recipe_portion_grams)
  - fatty_fish ≥ 2  раз/нед  (мягкий бонус: пока <2, candidates ужимаются до fish)
  - plant      ≥ 1  раз/день (мягкий бонус: пока за день =0, candidates ужимаются до plant)
Все нарушения уходят в self.last_warnings и далее в Menu.warnings.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe

from .exceptions import EmptyRolePoolError
from .portions import daily_target_grams, recipe_portion_grams  # MG_304_V_generator

logger = logging.getLogger(__name__)


MEAL_PLAN_3 = ["breakfast", "lunch", "dinner"]
MEAL_PLAN_5 = ["breakfast", "snack1", "lunch", "snack2", "dinner"]

MEAL_TYPE_DB = {
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "snack1": "snack",
    "snack2": "snack",
}

MEAL_COMPONENTS: Dict[str, Tuple[str, ...]] = {
    "breakfast": ("grain", "protein", "fruit"),
    "lunch": ("protein", "grain", "vegetable"),
    "dinner": ("protein", "grain", "vegetable"),
    "snack1": ("fruit", "dairy"),
    "snack2": ("protein", "vegetable"),
}

# MG_302_V_generator: недельные/дневные лимиты
RED_MEAT_MAX_GRAMS_PER_WEEK = 500  # ≤ 500 г/нед на члена семьи
FATTY_FISH_MIN_PER_WEEK = 2  # ≥ 2 раза/нед
PLANT_PROTEIN_MIN_PER_DAY = 1  # ≥ 1 раз/день

# MG_303_V_generator: распределение КБЖУ по приёмам пищи
MEAL_CALORIE_WEIGHTS_3 = {
    "breakfast": 0.25,
    "lunch": 0.40,
    "dinner": 0.35,
}
MEAL_CALORIE_WEIGHTS_5 = {
    "breakfast": 0.30,
    "snack1": 0.05,
    "lunch": 0.35,
    "snack2": 0.05,
    "dinner": 0.25,
}
# Окна эскалации (±доля от per-role target)
MEAL_CAL_WINDOW_TIERS = (0.15, 0.30, 0.50)

# MG_502_503_V_generator: контроль масла и сахара
DAILY_OIL_TSP_LIMIT = 5.0  # ≤ 5 ч.л. масла в сутки на члена семьи
OIL_TSP_HEAVY_THRESHOLD = 0.5  # рецепт считается «маслянистым» при oil_tsp > 0.5
SWEET_PER_DAY_LIMIT = 1  # ≤ 1 сладкого перекуса в день
MAIN_MEAL_TYPES = ("breakfast", "lunch", "dinner")  # сладкое запрещено

TIER_FEATURES = {
    "free": {"country": True},
    "lite": {"country": True, "disliked": True},
    "basic": {"country": True, "disliked": True, "calories": True},
    "basic_plus": {"country": True, "disliked": True, "calories": True, "fridge": True},
    "premium": {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
    "horeca": {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
}


class _WeeklyTracker:
    """
    Счётчики использований per (member_id).
    MG_302_V_generator:
      - red_meat_grams — суммарные граммы за скользящую неделю
      - fatty_fish     — раз в неделю
      - plant_per_day  — раз в день (для PLANT_PROTEIN_MIN_PER_DAY)
    """

    def __init__(self):
        # week_index -> member_id -> {"red_meat_grams": float, "fatty_fish": int}
        self._weekly: Dict[int, Dict[int, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"red_meat_grams": 0.0, "fatty_fish": 0})
        )
        # day_offset -> member_id -> {"plant": int, "animal": int, "mixed": int}
        # MG_502_503_V_generator: добавлены oil_tsp (float) и sweet_count (int)
        self._daily: Dict[int, Dict[int, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"plant": 0, "animal": 0, "mixed": 0, "oil_tsp": 0.0, "sweet_count": 0})
        )

    @staticmethod
    def week_of(day_offset: int) -> int:
        return day_offset // 7

    def get_week(self, member_id: int, day_offset: int) -> Dict[str, float]:
        return self._weekly[self.week_of(day_offset)][member_id]

    def get_day(self, member_id: int, day_offset: int) -> Dict[str, int]:
        return self._daily[day_offset][member_id]

    def add(self, member_id: int, day_offset: int, recipe: Recipe) -> None:
        w = self.get_week(member_id, day_offset)
        d = self.get_day(member_id, day_offset)

        if getattr(recipe, "is_red_meat", False):
            try:
                w["red_meat_grams"] += float(recipe_portion_grams(recipe) or 0.0)
            except Exception:
                pass
        if getattr(recipe, "is_fatty_fish", False):
            w["fatty_fish"] += 1

        ptype = getattr(recipe, "protein_type", None)
        if ptype in ("plant", "animal", "mixed"):
            d[ptype] += 1

        # MG_502_503_V_generator: oil_tsp и sweet_count
        oil = getattr(recipe, "oil_tsp", None)
        if oil is not None:
            try:
                d["oil_tsp"] = float(d.get("oil_tsp", 0.0)) + float(oil)
            except (TypeError, ValueError):
                pass
        if getattr(recipe, "has_added_sugar", False):
            d["sweet_count"] = int(d.get("sweet_count", 0)) + 1

    # для итоговых warning'ов
    def all_weeks(self) -> Dict[int, Dict[int, Dict[str, float]]]:
        return self._weekly

    def all_days(self) -> Dict[int, Dict[int, Dict[str, int]]]:
        return self._daily


class MenuGenerator:
    """Генератор меню по методу тарелки с учётом недельных/дневных ограничений."""

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
        # MG_605A_V_generator: режим мульти-член
        self.mode = str(self.filters.get("mode", "family"))
        if self.mode not in ("per_member", "family"):
            self.mode = "family"
        self.tracker = _WeeklyTracker()
        self.last_warnings: list = []
        # MG_303_V_generator: фактические ккал по (member_id, day_offset, meal_slot)
        self._meal_cal_actual: Dict[Tuple[int, int, str], float] = defaultdict(float)
        # MG_303_V_generator: целевые ккал по (member_id, day_offset, meal_slot) — для сборки warnings
        self._meal_cal_target: Dict[Tuple[int, int, str], Optional[float]] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def generate(self) -> List[dict]:
        # MG_605A_V_generator: режим family — один прогон, дублирование под членов
        if self.mode == "family" and len(self.members) > 1:
            return self._generate_family()
        all_recipes = self._build_recipe_pool()
        pools = self._build_pools_by_role(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items: List[dict] = []
        used_per_member: dict = {m.id: set() for m in self.members}

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)
                # MG_505_V_generate_loop: cheat-day detection
                _mg505_current_date = self.start_date + _mg505_timedelta(days=day)
                _mg505_is_cheat = _mg505_is_cheat_day(member, _mg505_current_date)
                _mg505_cheat_slot = _mg505_pick_cheat_slot(member.id, day) if _mg505_is_cheat else None

                for meal_slot in self.meal_types:

                    db_meal_type = MEAL_TYPE_DB[meal_slot]

                    roles = MEAL_COMPONENTS.get(meal_slot, ("other",))

                    # MG_303_V_generator: вес приёма из таблицы вместо равных долей

                    per_meal_cal = self._meal_target_cal(target_cal, meal_slot)

                    per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

                    self._meal_cal_target[(member.id, day, meal_slot)] = per_meal_cal

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
                            is_cheat=(
                                _mg505_is_cheat and meal_slot == _mg505_cheat_slot and role == "protein"
                            ),  # MG_505_V_generate_loop
                        )
                        if recipe is None:
                            err = EmptyRolePoolError(
                                role=role,
                                meal_slot=meal_slot,
                                day_offset=day,
                                member_name=self._member_display_name(member),
                            )
                            self._audit_empty_pool(err, member)
                            logger.warning(
                                "MG-301 empty role pool: role=%s slot=%s day=%s member=%s",
                                role,
                                meal_slot,
                                day,
                                member.id,
                            )
                            raise err
                        used_per_member[member.id].add(recipe.id)
                        self.tracker.add(member.id, day, recipe)
                        # MG_303_V_generator: суммируем ккал приёма
                        rcal = self._recipe_cal(recipe)
                        if rcal is not None:
                            self._meal_cal_actual[(member.id, day, meal_slot)] += float(rcal)
                        items.append(
                            {
                                "member": member,
                                "meal_type": db_meal_type,
                                "meal_slot": meal_slot,
                                "day_offset": day,
                                "recipe": recipe,
                                "component_role": role,
                                "is_cheat_meal": bool(
                                    _mg505_is_cheat and meal_slot == _mg505_cheat_slot
                                ),  # MG_505_V_generate_loop
                            }
                        )

        # MG_304_V_generator: добор овощей/фруктов
        warnings: list = []
        warnings.extend(
            self._ensure_veg_fruit_servings(
                items=items,
                pools=pools,
                used_per_member=used_per_member,
                fridge_ids=fridge_ids,
            )
        )

        # MG_302_V_generator: warnings по недельным/дневным лимитам
        warnings.extend(self._collect_weekly_warnings())
        warnings.extend(self._collect_daily_plant_warnings())

        # MG_303_V_generator: warnings по отклонению ккал приёма от target
        warnings.extend(self._collect_meal_calorie_warnings())

        # MG_502_503_V_generator: warnings по маслу и сладкому
        warnings.extend(self._collect_daily_oil_warnings())
        warnings.extend(self._collect_daily_sweet_warnings())

        self.last_warnings = warnings
        return items

    # ── MG-302: warnings collectors ──────────────────────────────────────────
    def _collect_weekly_warnings(self) -> list:
        out: list = []
        weeks_total = max(1, (self.period_days + 6) // 7)
        for w_idx in range(weeks_total):
            for member in self.members:
                # MG_302_V_generator: счётчик может отсутствовать, считаем 0-default
                c = self.tracker.all_weeks().get(w_idx, {}).get(member.id) or {}
                red_g = float(c.get("red_meat_grams", 0.0) or 0.0)
                fish = int(c.get("fatty_fish", 0) or 0)
                if red_g > RED_MEAT_MAX_GRAMS_PER_WEEK:
                    out.append(
                        {
                            "code": "red_meat_overlimit",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "week_index": w_idx,
                            "limit_grams": RED_MEAT_MAX_GRAMS_PER_WEEK,
                            "actual_grams": round(red_g, 1),
                        }
                    )
                if fish < FATTY_FISH_MIN_PER_WEEK:
                    out.append(
                        {
                            "code": "fatty_fish_shortfall",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "week_index": w_idx,
                            "min_count": FATTY_FISH_MIN_PER_WEEK,
                            "actual_count": fish,
                        }
                    )
        return out

    def _collect_daily_plant_warnings(self) -> list:
        out: list = []
        for day in range(self.period_days):
            for member in self.members:
                # MG_302_V_generator: счётчик может отсутствовать, считаем 0-default
                d = self.tracker.all_days().get(day, {}).get(member.id) or {}
                plant = int(d.get("plant", 0) or 0)
                if plant < PLANT_PROTEIN_MIN_PER_DAY:
                    out.append(
                        {
                            "code": "plant_protein_shortfall",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "day_offset": day,
                            "min_count": PLANT_PROTEIN_MIN_PER_DAY,
                            "actual_count": plant,
                        }
                    )
        return out

    # ── MG-304: добор порций овощей/фруктов ──────────────────────────────────
    def _ensure_veg_fruit_servings(self, items, pools, used_per_member, fridge_ids):
        warnings: list = []
        grams: dict = {}
        for it in items:
            if it.get("component_role") in ("vegetable", "fruit"):
                key = (it["member"].id, it["day_offset"])
                grams[key] = grams.get(key, 0.0) + recipe_portion_grams(it["recipe"])

        veg_fruit_pool = list(pools.get("vegetable", [])) + list(pools.get("fruit", []))

        existing_snack_slots = {}
        for it in items:
            slot = it.get("meal_slot", "") or ""
            if slot.startswith("snack"):
                key = (it["member"].id, it["day_offset"])
                existing_snack_slots[key] = existing_snack_slots.get(key, 0) + 1

        for member in self.members:
            target = daily_target_grams(member, ref_date=self.start_date)
            for day in range(self.period_days):
                key = (member.id, day)
                have = grams.get(key, 0.0)
                if have >= target:
                    continue

                hard_exclude = self._get_hard_exclude(member)
                added = 0
                MAX_ADD = 5
                while have < target and added < MAX_ADD:
                    candidate = None
                    for r in veg_fruit_pool:
                        if r.id in used_per_member[member.id]:
                            continue
                        if not self._recipe_passes_hard(r, hard_exclude):
                            continue
                        candidate = r
                        break

                    if candidate is None:
                        break

                    used_per_member[member.id].add(candidate.id)
                    base_idx = existing_snack_slots.get(key, 0)
                    slot_n = base_idx + added + 1
                    role = candidate.food_group if candidate.food_group in ("vegetable", "fruit") else "vegetable"
                    items.append(
                        {
                            "member": member,
                            "meal_type": "snack",
                            "meal_slot": f"snack{slot_n}",
                            "day_offset": day,
                            "recipe": candidate,
                            "component_role": role,
                            "is_virtual": True,  # MG_304_V_generator
                        }
                    )
                    have += recipe_portion_grams(candidate)
                    added += 1

                if have < target:
                    warnings.append(
                        {
                            "code": "veg_fruit_shortfall",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "day_offset": day,
                            "target_grams": round(target, 1),
                            "actual_grams": round(have, 1),
                            "missing_grams": round(target - have, 1),
                        }
                    )
        return warnings

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
            "protein": [],
            "grain": [],
            "vegetable": [],
            "fruit": [],
            "dairy": [],
            "oil": [],
            "other": [],
        }
        for r in recipes:
            fg = getattr(r, "food_group", None) or "other"
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
        is_cheat: bool = False,  # MG_505_V_pick_bypass
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
            candidates = [r for r in primary if r.id not in used and self._recipe_passes_hard(r, hard_exclude)]
        if not candidates:
            candidates = [r for r in primary if self._recipe_passes_hard(r, hard_exclude)]
        if not candidates and role != "other":
            candidates = [
                r for r in pools.get("other", []) if r.id not in used and self._recipe_passes_hard(r, hard_exclude)
            ]
        if not candidates:
            return None

        # MG_303_V_generator: эскалирующий калорийный фильтр ±15% → ±30% → ±50%
        # MG_505_V_pick_bypass: в cheat-meal не фильтруем по калориям
        if not is_cheat and target_cal and target_cal > 0:
            for tier in MEAL_CAL_WINDOW_TIERS:
                tol = float(target_cal) * float(tier)
                cal_ok = [
                    r
                    for r in candidates
                    if (c := self._recipe_cal(r)) is not None and abs(float(c) - float(target_cal)) <= tol
                ]
                if cal_ok:
                    candidates = cal_ok
                    break
            # Если ни одно окно не дало кандидатов — оставляем как есть (fallback random)
            # warning будет сгенерирован после факта в _collect_meal_calorie_warnings

        # MG_302_V_generator: недельные/дневные лимиты — только для protein
        # MG_505_V_pick_bypass: в cheat-meal не применяем MG-302 для protein
        if role == "protein" and not is_cheat:
            week = self.tracker.get_week(member_id, day_offset)
            day = self.tracker.get_day(member_id, day_offset)

            # 1) red_meat по граммам: если уже ≥ лимит — режем red_meat (с фолбэком)
            if week.get("red_meat_grams", 0.0) >= RED_MEAT_MAX_GRAMS_PER_WEEK:
                no_red = [r for r in candidates if not getattr(r, "is_red_meat", False)]
                if no_red:
                    candidates = no_red

            # 2) plant/день — приоритетнее, чем недельный fish-boost (правило ежедневное)
            if day.get("plant", 0) < PLANT_PROTEIN_MIN_PER_DAY:
                plant = [r for r in candidates if getattr(r, "protein_type", None) == "plant"]
                if plant:
                    candidates = plant
                    # plant найден — fish-boost ниже не применяем,
                    # чтобы не пересекать два правила в одном выборе
                else:
                    # plant нет в candidates — попробуем fish-boost
                    if week.get("fatty_fish", 0) < FATTY_FISH_MIN_PER_WEEK:
                        fish = [r for r in candidates if getattr(r, "is_fatty_fish", False)]
                        if fish:
                            candidates = fish
            else:
                # plant за день уже есть — обычный fish-boost
                if week.get("fatty_fish", 0) < FATTY_FISH_MIN_PER_WEEK:
                    fish = [r for r in candidates if getattr(r, "is_fatty_fish", False)]
                    if fish:
                        candidates = fish

        # MG_502_503_V_generator: контроль масла (≤5 ч.л./день)
        # MG_505_V_pick_bypass: в cheat-meal не режем масляные
        day_t = self.tracker.get_day(member_id, day_offset)
        if not is_cheat and float(day_t.get("oil_tsp", 0.0)) > DAILY_OIL_TSP_LIMIT:
            light = [r for r in candidates if (getattr(r, "oil_tsp", None) or 0) <= OIL_TSP_HEAVY_THRESHOLD]
            if light:
                candidates = light
            # если все кандидаты — «маслянистые», оставляем как есть, warning соберём после факта

        # MG_502_503_V_generator: исключение сахара
        # MG_505_V_pick_bypass: в cheat-meal сахар разрешён
        # 1) основные приёмы: has_added_sugar=True вообще запрещено
        if not is_cheat and meal_type in MAIN_MEAL_TYPES:
            no_sugar = [r for r in candidates if not getattr(r, "has_added_sugar", False)]
            if no_sugar:
                candidates = no_sugar
            # если все candidates сладкие (маловероятно для основных) — fallback random,
            # warning будет в _collect_daily_sweet_warnings
        # 2) snack: ≤ SWEET_PER_DAY_LIMIT сладких в день
        elif not is_cheat and meal_type == "snack":
            if int(day_t.get("sweet_count", 0)) >= SWEET_PER_DAY_LIMIT:
                no_sugar = [r for r in candidates if not getattr(r, "has_added_sugar", False)]
                if no_sugar:
                    candidates = no_sugar

        # Бонус по холодильнику
        if fridge_ids:
            candidates.sort(key=lambda r: self._fridge_score(r, fridge_ids), reverse=True)
            candidates = candidates[:10]

        return random.choice(candidates)

    # ── MG-303: meal calorie target / warnings ───────────────────────────────
    def _meal_target_cal(self, target_cal: Optional[int], meal_slot: str) -> Optional[float]:
        """MG_303_V_generator: возвращает целевые ккал на приём по таблице весов."""
        if not target_cal:
            return None
        weights = (
            MEAL_CALORIE_WEIGHTS_5 if str(self.filters.get("meal_plan_type", "3")) == "5" else MEAL_CALORIE_WEIGHTS_3
        )
        w = weights.get(meal_slot)
        if w is None:
            # fallback на равные доли
            return float(target_cal) / max(1, len(self.meal_types))
        return float(target_cal) * float(w)

    def _collect_meal_calorie_warnings(self) -> list:
        """MG_303_V_generator: warnings по отклонению фактических ккал приёма от целевых."""
        out: list = []
        max_tol = MEAL_CAL_WINDOW_TIERS[-1]  # 0.50
        for (member_id, day, meal_slot), target in self._meal_cal_target.items():
            if not target or target <= 0:
                continue
            actual = float(self._meal_cal_actual.get((member_id, day, meal_slot), 0.0) or 0.0)
            if actual <= 0:
                continue
            delta = actual - float(target)
            if abs(delta) > float(target) * max_tol:
                member = next((m for m in self.members if m.id == member_id), None)
                out.append(
                    {
                        "code": "meal_calorie_mismatch",
                        "member_id": member_id,
                        "member_name": self._member_display_name(member) if member else "",
                        "day_offset": day,
                        "meal_slot": meal_slot,
                        "target_cal": round(float(target), 1),
                        "actual_cal": round(actual, 1),
                        "delta_cal": round(delta, 1),
                        "delta_pct": round(delta / float(target) * 100.0, 1),
                    }
                )
        return out

    # ── helpers ──────────────────────────────────────────────────────────────

    # ── MG-502/503: oil & sugar warnings ──────────────────────────────────────
    def _collect_daily_oil_warnings(self) -> list:
        """MG_502_503_V_generator: warning oil_overlimit если суммарно за день >5 ч.л."""
        out: list = []
        days = sorted(self.tracker._daily.keys())
        for day in days:
            if day >= self.period_days:
                continue
            for member in self.members:
                d = self.tracker._daily[day].get(member.id)
                if not d:
                    continue
                actual = float(d.get("oil_tsp", 0.0))
                if actual > DAILY_OIL_TSP_LIMIT:
                    out.append(
                        {
                            "code": "oil_overlimit",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "day_offset": day,
                            "actual_tsp": round(actual, 1),
                            "limit_tsp": DAILY_OIL_TSP_LIMIT,
                            "delta_tsp": round(actual - DAILY_OIL_TSP_LIMIT, 1),
                        }
                    )
        return out

    def _collect_daily_sweet_warnings(self) -> list:
        """MG_502_503_V_generator: warning sweet_overlimit если за день >SWEET_PER_DAY_LIMIT сладких."""
        out: list = []
        days = sorted(self.tracker._daily.keys())
        for day in days:
            if day >= self.period_days:
                continue
            for member in self.members:
                d = self.tracker._daily[day].get(member.id)
                if not d:
                    continue
                cnt = int(d.get("sweet_count", 0))
                if cnt > SWEET_PER_DAY_LIMIT:
                    out.append(
                        {
                            "code": "sweet_overlimit",
                            "member_id": member.id,
                            "member_name": self._member_display_name(member),
                            "day_offset": day,
                            "sweet_count": cnt,
                            "limit": SWEET_PER_DAY_LIMIT,
                        }
                    )
        return out

    def _get_fridge_ingredient_names(self) -> set:
        if not self.features.get("fridge"):
            return set()
        items = FridgeItem.objects.filter(family=self.family, is_deleted=False)
        return {i.name.lower() for i in items}

    # MG_605A_V_generator: family-режим — один прогон, дублирование под членов
    def _generate_family(self) -> List[dict]:
        from .portions import member_quantity_for_recipe

        all_recipes = self._build_recipe_pool()
        pools = self._build_pools_by_role(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items: List[dict] = []

        virt = self._family_virtual_member()
        used: set = set()

        for day in range(self.period_days):
            target_cal = virt["calorie_target"]
            hard_exclude = virt["hard_exclude"]
            for meal_slot in self.meal_types:
                db_meal_type = MEAL_TYPE_DB[meal_slot]
                roles = MEAL_COMPONENTS.get(meal_slot, ("other",))
                per_meal_cal = self._meal_target_cal(target_cal, meal_slot)
                per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

                for m in self.members:
                    self._meal_cal_target[(m.id, day, meal_slot)] = per_meal_cal

                for role in roles:
                    recipe = self._pick_for_role(
                        role=role,
                        meal_type=db_meal_type,
                        pools=pools,
                        used=used,
                        hard_exclude=hard_exclude,
                        fridge_ids=fridge_ids,
                        target_cal=per_role_cal,
                        member_id=0,
                        day_offset=day,
                        is_cheat=False,
                    )
                    if recipe is None:
                        err = EmptyRolePoolError(
                            role=role,
                            meal_slot=meal_slot,
                            day_offset=day,
                            member_name="family",
                        )
                        logger.warning(
                            "MG-605A family empty role pool: role=%s slot=%s day=%s",
                            role,
                            meal_slot,
                            day,
                        )
                        raise err

                    used.add(recipe.id)
                    rcal = self._recipe_cal(recipe)

                    for member in self.members:
                        self.tracker.add(member.id, day, recipe)
                        if rcal is not None:
                            self._meal_cal_actual[(member.id, day, meal_slot)] += float(rcal)
                        items.append(
                            {
                                "member": member,
                                "meal_type": db_meal_type,
                                "meal_slot": meal_slot,
                                "day_offset": day,
                                "recipe": recipe,
                                "component_role": role,
                                "is_cheat_meal": False,
                                "quantity": round(
                                    member_quantity_for_recipe(member, recipe, ref_date=self.start_date), 2
                                ),
                            }
                        )

        used_per_member = {m.id: set(used) for m in self.members}
        warnings: list = []
        warnings.extend(
            self._ensure_veg_fruit_servings(
                items=items,
                pools=pools,
                used_per_member=used_per_member,
                fridge_ids=fridge_ids,
            )
        )
        warnings.extend(self._collect_weekly_warnings())
        warnings.extend(self._collect_daily_plant_warnings())
        warnings.extend(self._collect_meal_calorie_warnings())
        self.last_warnings = warnings
        return items

    # MG_605A_V_generator: «виртуальный представитель семьи»
    def _family_virtual_member(self) -> dict:
        exclude = set()
        cals = []
        for m in self.members:
            user = m.user
            if isinstance(user.allergies, list):
                exclude.update(a.lower() for a in user.allergies)
            if self.features.get("disliked") and isinstance(user.disliked_products, list):
                exclude.update(d.lower() for d in user.disliked_products)
            if self.features.get("calories"):
                try:
                    c = user.profile.calorie_target
                    if c:
                        cals.append(int(c))
                except Exception:
                    pass
        avg_cal = int(sum(cals) / len(cals)) if cals else None
        return {"hard_exclude": exclude, "calorie_target": avg_cal}

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

    # ── MG-301: helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _member_display_name(member) -> str:
        try:
            user = member.user
            name = (getattr(user, "name", "") or "").strip()
            if name:
                return name
            email = (getattr(user, "email", "") or "").strip()
            if email:
                return email.split("@", 1)[0]
        except Exception:
            pass
        return ""

    def _audit_empty_pool(self, err, member) -> None:
        try:
            from apps.sync.models import AuditLog

            AuditLog.objects.create(
                user=getattr(member, "user", None),
                action="menu.generate.empty_role_pool",
                entity_type="menu_generation",
                entity_id=f"family:{self.family.id}",
                old_values=None,
                new_values={
                    "role": err.role,
                    "meal_slot": err.meal_slot,
                    "day_offset": err.day_offset,
                    "member_id": getattr(member, "id", None),
                    "member_name": err.member_name,
                    "plan_code": self.plan_code,
                    "filters": self.filters,
                    "period_days": self.period_days,
                    "message": str(err),
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("MG-301: audit log write failed (non-fatal)")


# MG_505_V_generator: cheat-meal слот
from datetime import date as _mg505_date  # noqa: E402
from datetime import timedelta as _mg505_timedelta  # noqa: E402

CHEAT_MEAL_DEFAULT_INTERVAL = 10
CHEAT_MEAL_SLOTS = ("lunch", "dinner")  # cheat-meal случается в одном из этих слотов


def _mg505_is_cheat_day(member, current_date):
    """True если сегодня день cheat-meal по правилам профиля."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return False
    _interval = getattr(profile, "cheat_meal_interval", None)
    interval = _interval if _interval is not None else CHEAT_MEAL_DEFAULT_INTERVAL
    if interval <= 0:
        return False
    if not isinstance(current_date, _mg505_date):
        return False
    last = getattr(profile, "last_cheat_meal_date", None)
    if last is None:
        # первый раз — начинаем отсчёт от сегодня, cheat случится через interval дней
        return False
    return (current_date - last).days >= interval


def _mg505_pick_cheat_slot(member_id, day_offset):
    """Детерминированный выбор lunch/dinner для cheat-meal."""
    return CHEAT_MEAL_SLOTS[(int(member_id) + int(day_offset)) % len(CHEAT_MEAL_SLOTS)]


def _mg505_mark_cheat_meal_used(member, current_date):
    """Обновляет last_cheat_meal_date в профиле."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return
    profile.last_cheat_meal_date = current_date
    profile.save(update_fields=["last_cheat_meal_date"])
