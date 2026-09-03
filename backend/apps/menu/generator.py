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

from . import macro_roles as _mr  # MG_STRAT
from .exceptions import EmptyRolePoolError
from .portions import daily_target_grams, recipe_portion_grams  # MG_304_V_generator

logger = logging.getLogger(__name__)


MEAL_PLAN_3 = ["breakfast", "lunch", "dinner"]
MEAL_PLAN_5 = ["breakfast", "snack1", "lunch", "snack2", "dinner"]

# MG_MEALCOUNT: куда складывать доборы. Нового приёма пищи не создаём: человек
# выбрал три приёма — значит, три.
#
# Овощной добор (MG-304) идёт только в обед и ужин: салат есть в составе именно
# этих приёмов (см. MEAL_COMPONENTS), а на завтрак и в перекус он не ставится —
# состав приёма не должен меняться от того, добирали в этот день овощи или нет.
VEG_TOPUP_SLOTS = ("lunch", "dinner")

MEAL_TYPE_DB = {
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "snack1": "snack",
    "snack2": "snack",
}

# RB001_V_step4: роли тарелки = dish_type рецепта.
# Состав приёмов (порядок = порядок подбора):
#   breakfast      -> breakfast_dish, drink?
#   lunch          -> soup?, main, salad?, dessert?, bakery?
#   dinner         -> main, salad?
#   snack1/snack2  -> snack, drink?
# MG_DRINK: напитки исключены из генерации s1 (пул из 4 рецептов давал
# 100%-повторы во всех меню, а равная дележка калорий приёма забирала у еды
# половину бюджета завтрака/перекуса). В стратегиях 2 и 3 напитков и так нет.
MEAL_COMPONENTS: Dict[str, Tuple[str, ...]] = {
    "breakfast": ("breakfast_dish",),
    "lunch": ("soup", "main", "salad", "dessert", "bakery"),
    "dinner": ("main", "salad"),
    "snack1": ("snack",),
    "snack2": ("snack",),
}


# MG_SUITABLE: роли, у которых есть ВЫБОР приёма. Только для них фильтр по
# suitable_for что-то решает.
#
# suitable_for отвечает на вопрос «когда это едят», и по нему же отсеиваются
# кандидаты при подборе. Для роли, встречающейся в нескольких приёмах, это
# осмысленно: основное блюдо с пометкой «ужин» не надо ставить в обед, потому
# что у него есть куда пойти. Но роль «десерт» существует только в обеде, и
# пометка, где обеда нет, не выбирает между слотами — она вычёркивает рецепт
# целиком, потому что другого слота у него нет.
#
# Чем это обошлось (замер на проде, chat-83): импорт say7 помечал десерты как
# ["snack"], а выпечку как ["breakfast", "snack"] — вполне разумно на вид,
# десерт и правда сойдёт за перекус. Но перекус берёт блюда с dish_type='snack',
# а не десерты. В итоге из 45 десертов генератор доставал 5, из 35 выпечек — 2,
# остальные шли только по запасному пути, когда достижимые израсходованы. В
# отчёте mg_analyze_s1_repeats это читалось как «пять рецептов в 20 прогонах из
# 20» и как нехватка пула — хотя пул был.
#
# Чинить решили здесь, а не разметкой 630 рецептов: то же поле читает фильтр
# «приём пищи» в каталоге (apps/recipes/filters.py), и дописав туда «обед», мы
# высыпали бы человеку в выдачу по обеду четыреста наименований выпечки и двести
# десертов. Разметка отвечает на свой вопрос правильно — неправильно было
# спрашивать её там, где выбора нет.
#
# Набор ВЫВОДИТСЯ из MEAL_COMPONENTS, а не выписан руками: список, переписанный
# рядом, разошёлся бы с раскладкой приёмов ровно так же, как разошлась разметка
# импорта, и заметили бы это опять по повторяемости меню.
def _roles_with_meal_choice() -> frozenset:
    meals_by_role: Dict[str, set] = {}
    for meal_slot, roles in MEAL_COMPONENTS.items():
        db_meal_type = MEAL_TYPE_DB[meal_slot]
        for role in roles:
            meals_by_role.setdefault(role, set()).add(db_meal_type)
    return frozenset(role for role, meals in meals_by_role.items() if len(meals) > 1)


ROLES_WITH_MEAL_CHOICE = _roles_with_meal_choice()

# RB001_V_step4: обязательные роли — при пустом пуле поднимаем EmptyRolePoolError.
# Остальные роли опциональны: нет рецепта → пропускаем (continue), без ошибки.
REQUIRED_ROLES: Dict[str, Tuple[str, ...]] = {
    "breakfast": ("breakfast_dish",),
    "lunch": ("main",),
    "dinner": ("main",),
    "snack1": ("snack",),
    "snack2": ("snack",),
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
DESSERT_MAX_PER_DAY = 1  # MG_611_V_generator: ≤ 1 десерта+выпечки в день на члена семьи
MAIN_MEAL_TYPES = ("breakfast", "lunch", "dinner")  # сладкое запрещено

# MG_SWEETROLE: роли, где сладость — не порок, а определение.
#
# Запрет на has_added_sugar в основных приёмах писался, когда десертной роли в
# обеде ещё не было. Роль добавили позже (RB001_V_step4), и правило стало
# отрицать само себя: слот десерта живёт в обеде, обед — основной приём, значит
# в десертный слот проходят только десерты БЕЗ добавленного сахара.
#
# Чем это обошлось (замер на dev, chat-83): из 39 десертов таких оказалось три —
# и ровно они стояли в 20 меню из 20. Остальные тридцать шесть получали слот
# только на четвёртый-пятый день, когда несладкие уже израсходованы; в отчёте
# mg_analyze_s1_repeats это выглядело как «три вечных десерта» и длинный хвост
# по 1–6 прогонов из 20. У выпечки то же самое, мягче: 7 несладких из 19.
#
# Сахара в дне от этого больше не станет: DESSERT_MAX_PER_DAY уже держит десерт
# и выпечку вместе на одной штуке в сутки, а SWEET_PER_DAY_LIMIT продолжает
# работать для перекусов. Снимается не ограничение количества, а требование,
# чтобы сладкое блюдо было несладким.
SWEET_ROLES = frozenset({"dessert", "bakery"})

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
            lambda: defaultdict(
                lambda: {
                    "plant": 0,
                    "animal": 0,
                    "mixed": 0,
                    "oil_tsp": 0.0,
                    "sweet_count": 0,
                    "dessert_count": 0,
                    "bakery_count": 0,
                }
            )
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
        # MG_611_V_generator: track desserts and bakery
        if getattr(recipe, "dish_type", None) == "dessert":
            d["dessert_count"] = int(d.get("dessert_count", 0)) + 1
        if getattr(recipe, "dish_type", None) == "bakery":
            d["bakery_count"] = int(d.get("bakery_count", 0)) + 1

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
        # MG_610_V_generator: with_soup
        _with_soup = self.filters.get("with_soup", True)
        self.with_soup: bool = _with_soup is not False
        # MG_STRAT: 1=current, 2=composition, 3=plate
        self.strategy = str(self.filters.get("strategy", "1") or "1")
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
        # MG_610_V_generator: align start_date to Monday
        from datetime import timedelta as _td610

        _wd = self.start_date.weekday()
        if _wd != 0:
            self.start_date = self.start_date - _td610(days=_wd)
        # MG_STRAT: alternative strategies (per_member only for now)
        if self.strategy == "2":
            return self._generate_strategy2()
        if self.strategy == "3":
            return self._generate_strategy3()
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

                    # RB001_V_step4: ккал делим поровну на число ролей приёма
                    per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

                    self._meal_cal_target[(member.id, day, meal_slot)] = per_meal_cal
                    required = REQUIRED_ROLES.get(meal_slot, ())

                    for role in roles:
                        # MG_610_V_generator: soup toggle
                        if role == "soup" and not self.with_soup:
                            continue
                        # MG_611_V_generator: dessert+bakery combined limit
                        if role in ("dessert", "bakery"):
                            _d611 = self.tracker.get_day(member.id, day)
                            _sweet = int(_d611.get("dessert_count", 0)) + int(_d611.get("bakery_count", 0))
                            if _sweet >= DESSERT_MAX_PER_DAY:
                                continue
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
                                _mg505_is_cheat and meal_slot == _mg505_cheat_slot and role == "main"
                            ),  # MG_505_V_generate_loop
                        )
                        if recipe is None:
                            # RB001_V_step4: опциональная роль — просто пропускаем
                            if role not in required:
                                continue
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

    # MG_MEALCOUNT: слоты для доборов — только те, что есть в выбранном плане.
    #
    # Раньше добор всегда создавал новые перекусы: snack1, snack2, дальше snack3
    # и так до пяти. В плане на три приёма это превращало «завтрак, обед, ужин» в
    # пять приёмов, а snack3+ вообще не показывался — ни в вебе, ни в мобильном:
    # оба рисуют ровно слоты выбранного плана. То есть блюда подбирались, лежали
    # в меню, попадали в список покупок — и не были видны.
    #
    # Порядок: сначала перекусы (если план на пять) — там добору самое место, —
    # затем обед и ужин.
    def _snack_topup_slots(self) -> tuple:
        snacks = tuple(s for s in self.meal_types if s.startswith("snack"))
        return snacks + VEG_TOPUP_SLOTS

    @staticmethod
    def _occupied_pairs(items) -> set:
        """(member, день, слот, роль) — что уже занято.

        В menu_items на эту четвёрку стоит UNIQUE: в одном приёме роль бывает
        только одна. Поэтому добор не «дописывается» в приём вслепую, а ищет
        свободную роль.
        """
        return {(it["member"].id, it["day_offset"], it.get("meal_slot"), it.get("component_role")) for it in items}

    @staticmethod
    def _free_topup_slot(slots, occupied: set, member_id: int, day: int, role: str):
        """Первый слот, где эта роль ещё свободна. None — ставить некуда."""
        for slot in slots:
            if (member_id, day, slot, role) not in occupied:
                return slot
        return None

    # ── MG-304: добор порций овощей/фруктов ──────────────────────────────────
    def _ensure_veg_fruit_servings(self, items, pools, used_per_member, fridge_ids):
        warnings: list = []
        grams: dict = {}
        for it in items:
            # RB001_V_step4: овощную долю даёт роль salad
            if it.get("component_role") == "salad":
                key = (it["member"].id, it["day_offset"])
                grams[key] = grams.get(key, 0.0) + recipe_portion_grams(it["recipe"])

        veg_fruit_pool = list(pools.get("salad", []))
        occupied = self._occupied_pairs(items)  # MG_MEALCOUNT

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

                    # MG_MEALCOUNT: добор идёт в приём выбранного плана, а не в
                    # новый перекус. Мест конечное число — остаток уйдёт в
                    # предупреждение veg_fruit_shortfall ниже.
                    role = "salad"  # RB001_V_step4
                    slot = self._free_topup_slot(VEG_TOPUP_SLOTS, occupied, member.id, day, role)
                    if slot is None:
                        break

                    used_per_member[member.id].add(candidate.id)
                    occupied.add((member.id, day, slot, role))
                    items.append(
                        {
                            "member": member,
                            "meal_type": MEAL_TYPE_DB[slot],
                            "meal_slot": slot,
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
        # MG_607_V_generator: countries (list) имеет приоритет над country (str)
        countries = self.filters.get("countries")
        country = self.filters.get("country")
        if self.features.get("country"):
            if countries:
                qs = qs.filter(country__in=list(countries))
            elif country:
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
        # RB001_V_step4: пулы по dish_type рецепта (роль тарелки = dish_type)
        pools: Dict[str, List[Recipe]] = {
            "breakfast_dish": [],
            "soup": [],
            "main": [],
            "salad": [],
            "side": [],
            "dessert": [],
            "drink": [],
            "bakery": [],
            "sauce": [],
            "snack": [],
            "other": [],
        }
        for r in recipes:
            dt = getattr(r, "dish_type", None) or "other"
            pools.setdefault(dt, []).append(r)
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
            # MG_SUITABLE: спрашиваем разметку только там, где у роли есть выбор
            # приёма. У десерта, выпечки и супа слот один — пометка не выбирала
            # бы между слотами, а вычёркивала рецепт целиком.
            if role in ROLES_WITH_MEAL_CHOICE:
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
        if role == "main" and not is_cheat:  # RB001_V_step4: protein-лимиты на основное блюдо
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
        # 1) основные приёмы: has_added_sugar=True вообще запрещено —
        #    кроме ролей, которые сами по себе сладкие (см. SWEET_ROLES).
        if not is_cheat and meal_type in MAIN_MEAL_TYPES and role not in SWEET_ROLES:
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
        # MG_610_V_generator: align start_date to Monday
        from datetime import timedelta as _td610f

        from .portions import member_quantity_for_recipe

        _wd = self.start_date.weekday()
        if _wd != 0:
            self.start_date = self.start_date - _td610f(days=_wd)

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

                required = REQUIRED_ROLES.get(meal_slot, ())  # RB001_V_step4
                for role in roles:
                    # MG_610_V_generator: soup toggle
                    if role == "soup" and not self.with_soup:
                        continue
                    # MG_611_V_generator: dessert+bakery combined limit
                    if role in ("dessert", "bakery"):
                        _d611f = self.tracker.get_day(0, day)
                        _sweet_f = int(_d611f.get("dessert_count", 0)) + int(_d611f.get("bakery_count", 0))
                        if _sweet_f >= DESSERT_MAX_PER_DAY:
                            continue
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
                        # RB001_V_step4: опциональная роль — пропускаем
                        if role not in required:
                            continue
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

    # MG_ALLERGEN14: аллерген из профиля — либо ключ из 14 (ТР ТС 022, тогда
    # матч по размеченному recipe.allergens), либо произвольный текст (тогда
    # подстрочный матч по именам ингредиентов). Дизлайки — всегда подстрочно.
    @staticmethod
    def _split_allergies(items):
        """→ (allergen_keys:set, custom_substrings:set)."""
        from apps.common.allergens import resolve_allergy

        keys = set()
        subs = set()
        for a in items or []:
            if not isinstance(a, str):
                continue
            k = resolve_allergy(a)
            if k:
                keys.add(k)
            else:
                t = a.strip().lower()
                if t:
                    subs.add(t)
        return keys, subs

    # MG_605A_V_generator: «виртуальный представитель семьи»
    def _family_virtual_member(self) -> dict:
        # MG_607_V_generator: per-request override
        override_a = self.filters.get("exclude_allergens")
        override_d = self.filters.get("exclude_disliked")
        akeys = set()
        subs = set()
        cals = []
        if override_a is not None:
            k, s = self._split_allergies(override_a)
            akeys |= k
            subs |= s
        if override_d is not None and self.features.get("disliked"):
            subs.update(d.lower() for d in override_d if isinstance(d, str))
        for m in self.members:
            user = m.user
            if override_a is None and isinstance(user.allergies, list):
                k, s = self._split_allergies(user.allergies)
                akeys |= k
                subs |= s
            if override_d is None and self.features.get("disliked") and isinstance(user.disliked_products, list):
                subs.update(d.lower() for d in user.disliked_products)
            if self.features.get("calories"):
                try:
                    c = user.profile.calorie_target
                    if c:
                        cals.append(int(c))
                except Exception:
                    pass
        avg_cal = int(sum(cals) / len(cals)) if cals else None
        return {"hard_exclude": {"allergens": akeys, "substr": subs}, "calorie_target": avg_cal}

    def _get_hard_exclude(self, member) -> dict:
        # MG_607_V_generator: per-request override через filters.exclude_allergens / exclude_disliked
        override_a = self.filters.get("exclude_allergens")
        override_d = self.filters.get("exclude_disliked")
        akeys = set()
        subs = set()
        user = member.user
        if override_a is not None:
            k, s = self._split_allergies(override_a)
            akeys |= k
            subs |= s
        elif isinstance(user.allergies, list):
            k, s = self._split_allergies(user.allergies)
            akeys |= k
            subs |= s
        if override_d is not None:
            if self.features.get("disliked"):
                subs.update(d.lower() for d in override_d if isinstance(d, str))
        elif self.features.get("disliked") and isinstance(user.disliked_products, list):
            subs.update(d.lower() for d in user.disliked_products)
        if override_a is None and self.features.get("allergies_family"):
            for m in self.members:
                if isinstance(m.user.allergies, list):
                    k, s = self._split_allergies(m.user.allergies)
                    akeys |= k
                    subs |= s
        return {"allergens": akeys, "substr": subs}

    def _get_calorie_target(self, member) -> Optional[int]:
        if not self.features.get("calories"):
            return None
        try:
            return member.user.profile.calorie_target
        except Exception:
            return None

    def _recipe_passes_hard(self, recipe: Recipe, hard_exclude: dict) -> bool:
        if not hard_exclude:
            return True
        akeys = hard_exclude.get("allergens")
        if akeys and set(recipe.allergens or []) & akeys:
            return False
        subs = hard_exclude.get("substr")
        if subs:
            for ing in recipe.ingredients:
                name = ing.get("name", "").lower()
                if any(ex in name for ex in subs):
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

    # ── MG_STRAT: helpers & alternative strategies ────────────────────────────
    _MACRO_ROLE_RU = {
        "protein": "белковый компонент",
        "fat": "жировой компонент (сыр/масло)",
        "carb_complex": "сложный углевод (крупа/хлеб)",
        "carb_simple": "простой углевод",
        "fiber": "клетчатка (овощи/фрукты)",
        "carb": "углевод",
    }

    def _recipe_kcal_portion(self, recipe):
        """MG_STRAT: калории одной порции (надёжный источник: kcal -> kcal_per_100g*portion_g -> nutrition)."""
        k = getattr(recipe, "kcal", None)
        if k is not None:
            try:
                return float(k)
            except (TypeError, ValueError):
                pass
        try:
            k100 = getattr(recipe, "kcal_per_100g", None)
            pg = getattr(recipe, "portion_g", None)
            if k100 is not None and pg:
                return float(k100) * float(pg) / 100.0
        except (TypeError, ValueError):
            pass
        return self._recipe_cal(recipe)

    def _build_role_pools_s2(self, recipes):
        """MG_STRAT: macro-role -> [recipes] (presence по ингредиентам)."""
        pools = {r: [] for r in (_mr.PROTEIN, _mr.FAT, _mr.CARB_COMPLEX, _mr.CARB_SIMPLE, _mr.FIBER)}
        for rec in recipes:
            for role in _mr.recipe_roles(rec):
                if role in pools:
                    pools[role].append(rec)
        return pools

    def _pick_role_addon_s2(self, role, meal_type, role_pools, used, hard_exclude, fridge_ids):
        """MG_STRAT: добор рецепта, закрывающего макро-роль (без калорийного фильтра)."""
        if role == "carb":
            primary = role_pools.get(_mr.CARB_COMPLEX, []) + role_pools.get(_mr.CARB_SIMPLE, [])
        else:
            primary = role_pools.get(role, [])
        cands = []
        for r in primary:
            if r.id in used:
                continue
            if not self._recipe_passes_hard(r, hard_exclude):
                continue
            # MG_SUITABLE: см. ROLES_WITH_MEAL_CHOICE — у роли с единственным
            # слотом разметка не выбирает, а только вычёркивает.
            if role in ROLES_WITH_MEAL_CHOICE:
                sf = getattr(r, "suitable_for", None)
                if sf and meal_type not in sf:
                    continue
            cands.append(r)
        if not cands:
            cands = [r for r in primary if r.id not in used and self._recipe_passes_hard(r, hard_exclude)]
        if not cands:
            return None
        if fridge_ids:
            cands.sort(key=lambda r: self._fridge_score(r, fridge_ids), reverse=True)
            cands = cands[:10]
        return random.choice(cands)

    def _place_s2(
        self, items, member, db_meal_type, meal_slot, day, recipe, used, component_role=None
    ):  # MG_STRAT2_ROLE
        """MG_STRAT: положить выбранный рецепт в items + учёт в tracker/калориях."""
        used.add(recipe.id)
        self.tracker.add(member.id, day, recipe)
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
                "component_role": component_role or (getattr(recipe, "dish_type", None) or "other"),  # MG_STRAT2_ROLE
                "is_cheat_meal": False,
            }
        )

    def _fill_snacks_s2(self, items, member, day, used, hard_exclude, fridge_ids, pools, target_cal):
        """MG_STRAT: добор до дневного КБЖУ (±5% по калориям).

        MG_MEALCOUNT: добор кладётся в слоты выбранного плана. В плане на пять
        приёмов это перекусы — как и раньше; в плане на три еда уходит в обед и
        ужин. Раньше слот назывался snack1, snack2 всегда, из-за чего меню на три
        приёма показывалось как пять.
        """
        day_sum = 0.0
        for it in items:
            if it["member"].id == member.id and it["day_offset"] == day:
                k = self._recipe_kcal_portion(it["recipe"])
                if k:
                    day_sum += float(k)
        snack_pool = list(pools.get("snack", []))
        occupied = self._occupied_pairs(items)  # MG_MEALCOUNT
        lo = target_cal * 0.95
        added = 0
        MAX_ADD = 5
        while day_sum < lo and added < MAX_ADD:
            remaining = target_cal - day_sum
            cands = [r for r in snack_pool if r.id not in used and self._recipe_passes_hard(r, hard_exclude)]
            if not cands:
                break
            fit = [r for r in cands if 0 < (self._recipe_kcal_portion(r) or 0) <= remaining * 1.05]
            rec = random.choice(fit if fit else cands)
            role = getattr(rec, "dish_type", None) or "snack"
            # MG_MEALCOUNT: свободное место в приёме выбранного плана; нет мест —
            # добор заканчиваем, недобор калорий уйдёт в предупреждения.
            slot = self._free_topup_slot(self._snack_topup_slots(), occupied, member.id, day, role)
            if slot is None:
                break
            self.tracker.add(member.id, day, rec)
            used.add(rec.id)
            occupied.add((member.id, day, slot, role))
            items.append(
                {
                    "member": member,
                    "meal_type": MEAL_TYPE_DB[slot],
                    "meal_slot": slot,
                    "day_offset": day,
                    "recipe": rec,
                    "component_role": role,
                    "is_cheat_meal": False,
                }
            )
            day_sum += float(self._recipe_kcal_portion(rec) or 0)
            added += 1

    def _generate_strategy2(self):
        """MG_STRAT strategy=2: состав приёма по макро-ролям (presence) + добор перекусов.
        per_member; MG-302/303/304/502/503 поверх; raise при непокрытой обязательной роли."""
        all_recipes = self._build_recipe_pool()
        # prefetch ролевых данных одним заходом
        _ids = [r.id for r in all_recipes]
        _pf = Recipe.objects.filter(id__in=_ids).prefetch_related("product_links__product__category_fk")
        _by = {r.id: r for r in _pf}
        all_recipes = [_by[i] for i in _ids if i in _by]

        pools = self._build_pools_by_role(all_recipes)
        role_pools = self._build_role_pools_s2(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items = []
        used_per_member = {m.id: set() for m in self.members}

        MEALS = ["breakfast", "lunch", "dinner"]
        MEAL_ROLES = {
            "breakfast": (_mr.PROTEIN, _mr.FAT, "carb", _mr.FIBER),
            "lunch": (_mr.PROTEIN, _mr.CARB_COMPLEX, _mr.FIBER),
            "dinner": (_mr.PROTEIN, _mr.FIBER),
        }
        ANCHOR_DT = {"breakfast": "breakfast_dish", "lunch": "main", "dinner": "main"}

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)
                used = used_per_member[member.id]
                lunch_has_carb = False

                for meal_slot in MEALS:
                    db_meal_type = MEAL_TYPE_DB[meal_slot]
                    per_meal_cal = self._meal_target_cal(target_cal, meal_slot)
                    self._meal_cal_target[(member.id, day, meal_slot)] = per_meal_cal

                    anchor_dt = ANCHOR_DT[meal_slot]
                    anchor = self._pick_for_role(
                        role=anchor_dt,
                        meal_type=db_meal_type,
                        pools=pools,
                        used=used,
                        hard_exclude=hard_exclude,
                        fridge_ids=fridge_ids,
                        target_cal=per_meal_cal,
                        member_id=member.id,
                        day_offset=day,
                    )
                    if anchor is None:
                        raise EmptyRolePoolError(
                            role=anchor_dt,
                            meal_slot=meal_slot,
                            day_offset=day,
                            member_name=self._member_display_name(member),
                        )
                    self._place_s2(
                        items, member, db_meal_type, meal_slot, day, anchor, used, component_role=anchor_dt
                    )  # MG_STRAT2_ROLE
                    covered = set(_mr.recipe_roles(anchor))

                    for role in MEAL_ROLES[meal_slot]:
                        if role == "carb":
                            if covered & _mr.CARB_ANY:
                                continue
                        elif role in covered:
                            continue
                        rec = self._pick_role_addon_s2(role, db_meal_type, role_pools, used, hard_exclude, fridge_ids)
                        if rec is None:
                            raise EmptyRolePoolError(
                                role=role,
                                meal_slot=meal_slot,
                                day_offset=day,
                                member_name=self._member_display_name(member),
                                reason_hint=f"Не хватает рецептов: {self._MACRO_ROLE_RU.get(role, role)}.",
                            )
                        self._place_s2(
                            items, member, db_meal_type, meal_slot, day, rec, used, component_role=str(role)
                        )  # MG_STRAT2_ROLE
                        covered |= _mr.recipe_roles(rec)

                    if meal_slot == "lunch":
                        lunch_has_carb = bool(covered & _mr.CARB_ANY)
                    elif meal_slot == "dinner" and not lunch_has_carb and not (covered & {_mr.CARB_COMPLEX}):
                        rec = self._pick_role_addon_s2(
                            _mr.CARB_COMPLEX, db_meal_type, role_pools, used, hard_exclude, fridge_ids
                        )
                        if rec is not None:
                            self._place_s2(
                                items,
                                member,
                                db_meal_type,
                                meal_slot,
                                day,
                                rec,
                                used,
                                component_role=str(_mr.CARB_COMPLEX),
                            )  # MG_STRAT2_ROLE

                if target_cal:  # MG_STRAT3: перекусы-добор по КБЖУ безусловны
                    self._fill_snacks_s2(items, member, day, used, hard_exclude, fridge_ids, pools, float(target_cal))

        warnings = []
        # MG_STRAT3: MG-304 (овощной добор) отключён для s2
        warnings.extend(self._collect_weekly_warnings())
        warnings.extend(self._collect_daily_plant_warnings())
        warnings.extend(self._collect_meal_calorie_warnings())
        warnings.extend(self._collect_daily_oil_warnings())
        warnings.extend(self._collect_daily_sweet_warnings())
        self.last_warnings = warnings
        return items

    # ── MG_STRAT3: strategy=3 (plate 25/25/50) ────────────────────────────────
    # MG_STRAT3_PLATEFORM: форма тарелки задаётся (per-component scaling), а не ищется.
    PLATE_SHARES = {"protein": 0.25, "carb": 0.25, "veg": 0.50}
    PLATE_MASS_DEFAULT_G = 400.0  # масса тарелки при отсутствии калор. цели
    PLATE_MASS_MIN_G = 200.0
    PLATE_MASS_MAX_G = 900.0
    PLATE_ITEM_Q_MIN = 0.25
    PLATE_ITEM_Q_MAX = 3.0
    PLATE_PICK_K = 30  # MG_STRAT3_SELECT: сколько троек сэмплировать и брать лучшую

    def _build_plate_pools_s3(self, recipes):
        """MG_STRAT3: plate_component -> [recipes] (ручная разметка)."""
        pools = {"protein": [], "carb": [], "veg": []}
        for r in recipes:
            pc = getattr(r, "plate_component", None)
            if pc in pools:
                pools[pc].append(r)
        return pools

    def _portion_g(self, recipe):
        pg = getattr(recipe, "portion_g", None)
        try:
            return float(pg) if pg else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _kcal_per_g(self, recipe):  # MG_STRAT3_PLATEFORM
        """ккал на 1 г порции рецепта (kcal_per_100g/100, либо kcal_порции/portion_g)."""
        kpg = getattr(recipe, "kcal_per_100g", None)
        if kpg:
            try:
                return float(kpg) / 100.0
            except (TypeError, ValueError):
                pass
        kc = self._recipe_kcal_portion(recipe)
        g = self._portion_g(recipe)
        if kc and g > 0:
            return float(kc) / g
        return 0.0

    def _pick_plate_s3(self, plate_pools, used, hard_exclude, meal_type, target_meal_cal):
        """MG_STRAT3_PLATEFORM: тройка (protein, carb, veg) + per-component quantity.
        Форма 25/25/50 ЗАДАЁТСЯ масштабом каждого компонента под массу тарелки M
        (M подбирается под target_meal_cal, при отсутствии — PLATE_MASS_DEFAULT_G).
        Возврат: (p, c, v, qp, qc, qv) или None."""

        def _flt(pool):
            out = []
            for r in pool:
                if r.id in used:
                    continue
                if not self._recipe_passes_hard(r, hard_exclude):
                    continue
                sf = getattr(r, "suitable_for", None)
                if sf and meal_type not in sf:
                    continue
                if self._portion_g(r) <= 0:
                    continue
                out.append(r)
            return out

        P, C, V = (
            _flt(plate_pools.get("protein", [])),
            _flt(plate_pools.get("carb", [])),
            _flt(plate_pools.get("veg", [])),
        )
        if not (P and C and V):
            return None

        sh = self.PLATE_SHARES

        def _eval(p, c, v):  # MG_STRAT3_SELECT: масса тарелки M + клампнутые quantity + ошибки
            if target_meal_cal:
                dens = (
                    sh["protein"] * self._kcal_per_g(p)
                    + sh["carb"] * self._kcal_per_g(c)
                    + sh["veg"] * self._kcal_per_g(v)
                )  # ккал на 1 г тарелки
                M = (float(target_meal_cal) / dens) if dens > 0 else self.PLATE_MASS_DEFAULT_G
            else:
                M = self.PLATE_MASS_DEFAULT_G
            M = max(self.PLATE_MASS_MIN_G, min(self.PLATE_MASS_MAX_G, M))

            def _q(recipe, share):
                g = self._portion_g(recipe)
                if g <= 0:
                    return 1.0
                q = (share * M) / g
                return round(max(self.PLATE_ITEM_Q_MIN, min(self.PLATE_ITEM_Q_MAX, q)), 2)

            qp = _q(p, sh["protein"])
            qc = _q(c, sh["carb"])
            qv = _q(v, sh["veg"])
            gp, gc, gv = self._portion_g(p) * qp, self._portion_g(c) * qc, self._portion_g(v) * qv
            tot = gp + gc + gv
            if tot <= 0:
                return (9.9, qp, qc, qv)
            form_err = abs(gp / tot - sh["protein"]) + abs(gc / tot - sh["carb"]) + abs(gv / tot - sh["veg"])
            if target_meal_cal:
                cal = sum((self._recipe_kcal_portion(r) or 0) * q for r, q in ((p, qp), (c, qc), (v, qv)))
                cal_err = abs(float(cal) - float(target_meal_cal)) / float(target_meal_cal)
            else:
                cal_err = 0.0
            return (form_err + cal_err, qp, qc, qv)

        best = None  # (score, p, c, v, qp, qc, qv)
        for _ in range(self.PLATE_PICK_K):
            p = random.choice(P)
            c = random.choice(C)
            v = random.choice(V)
            score, qp, qc, qv = _eval(p, c, v)
            if best is None or score < best[0]:
                best = (score, p, c, v, qp, qc, qv)
        if best is None:
            return None
        return (best[1], best[2], best[3], best[4], best[5], best[6])

    def _generate_strategy3(self):
        """MG_STRAT3 strategy=3: тарелка 25/25/50 по массе порций (±10%) + масштаб k∈[0.5,2.0] под КБЖУ.
        per_member; MG-303/304 off; MG-302 поверх (через warnings); перекусы — отдельным параметром позже."""
        all_recipes = self._build_recipe_pool()
        plate_pools = self._build_plate_pools_s3(all_recipes)
        items = []
        used_per_member = {m.id: set() for m in self.members}
        MEALS = ["breakfast", "lunch", "dinner"]

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)
                used = used_per_member[member.id]
                per_meal_cal = (float(target_cal) / 3.0) if target_cal else None

                for meal_slot in MEALS:
                    db_meal_type = MEAL_TYPE_DB[meal_slot]
                    self._meal_cal_target[(member.id, day, meal_slot)] = per_meal_cal
                    plate = self._pick_plate_s3(plate_pools, used, hard_exclude, db_meal_type, per_meal_cal)
                    if plate is None:
                        raise EmptyRolePoolError(
                            role="plate",
                            meal_slot=meal_slot,
                            day_offset=day,
                            member_name=self._member_display_name(member),
                            reason_hint=(
                                "Нет тройки рецептов (белок/гарнир/овощи) " "с разметкой тарелки и формой 25/25/50."
                            ),
                        )
                    p, c, v, qp, qc, qv = plate  # MG_STRAT3_PLATEFORM
                    _S3_ROLE = {"protein": "main", "carb": "side", "veg": "salad"}  # MG_STRAT3_ROLE
                    for rec, q, _pc in ((p, qp, "protein"), (c, qc, "carb"), (v, qv, "veg")):  # MG_STRAT3_ROLE
                        used.add(rec.id)
                        self.tracker.add(member.id, day, rec)
                        kc = self._recipe_kcal_portion(rec)
                        if kc is not None:
                            self._meal_cal_actual[(member.id, day, meal_slot)] += float(kc) * float(q)
                        items.append(
                            {
                                "member": member,
                                "meal_type": db_meal_type,
                                "meal_slot": meal_slot,
                                "day_offset": day,
                                "recipe": rec,
                                "component_role": _S3_ROLE[_pc],  # MG_STRAT3_ROLE
                                "is_cheat_meal": False,
                                "quantity": float(q),
                            }
                        )

        warnings = []
        warnings.extend(self._collect_weekly_warnings())
        warnings.extend(self._collect_daily_plant_warnings())
        warnings.extend(self._collect_meal_calorie_warnings())
        self.last_warnings = warnings
        return items


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
