import random
from datetime import date
from typing import List, Optional

from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

# Тарифные флаги, влияющие на алгоритм
TIER_FEATURES = {
    "free": {"country": True},
    "lite": {"country": True, "disliked": True},
    "basic": {"country": True, "disliked": True, "calories": True},
    "basic_plus": {"country": True, "disliked": True, "calories": True, "fridge": True},
    "premium": {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
    "horeca": {"country": True, "disliked": True, "calories": True, "fridge": True, "allergies_family": True},
}


class MenuGenerator:
    """
    Генерирует MenuItem-объекты для заданных членов семьи и набора дней.

    Приоритеты (жёсткие → мягкие):
      1. Аллергии (жёстко)
      2. Нелюбимые продукты (жёстко)
      3. Продукты в холодильнике (мягко, бонус при отборе)
      4. Калорийность (мягко, целевой коридор ±200 ккал)
      5. Разнообразие (не повторять рецепт в пределах периода)
      6. Страна (фильтр)
    """

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

    # ── public ────────────────────────────────────────────────────────────────

    def generate(self) -> List[dict]:
        """Возвращает список dict с полями: member, meal_type, day_offset, recipe."""
        pool = self._build_recipe_pool()
        fridge_ids = self._get_fridge_ingredient_names()
        items = []
        used_per_member: dict = {m.id: set() for m in self.members}

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)

                for meal_type in MEAL_TYPES:
                    recipe = self._pick_recipe(
                        pool=pool,
                        used=used_per_member[member.id],
                        hard_exclude=hard_exclude,
                        fridge_ids=fridge_ids,
                        target_cal=target_cal,
                        meal_type=meal_type,
                    )
                    if recipe:
                        used_per_member[member.id].add(recipe.id)
                        items.append(
                            {
                                "member": member,
                                "meal_type": meal_type,
                                "day_offset": day,
                                "recipe": recipe,
                            }
                        )
        return items

    # ── private ───────────────────────────────────────────────────────────────

    def _build_recipe_pool(self) -> List[Recipe]:
        qs = Recipe.objects.filter(is_published=True)

        country = self.filters.get("country")
        if country and self.features.get("country"):
            qs = qs.filter(country__iexact=country)

        max_time = self.filters.get("max_cook_time")
        if max_time:
            # cook_time хранится как строка "X мин", фильтруем в Python после загрузки
            qs = qs.exclude(cook_time="")

        recipes = list(qs.order_by("?")[:1000])
        max_time = self.filters.get("max_cook_time")
        if max_time:
            def _minutes(ct):
                try:
                    return int(str(ct).split()[0])
                except Exception:
                    return 9999
            recipes = [r for r in recipes if _minutes(r.cook_time) <= int(max_time)]
        return recipes[:500]

    def _get_fridge_ingredient_names(self) -> set:
        if not self.features.get("fridge"):
            return set()
        items = FridgeItem.objects.filter(family=self.family, is_deleted=False)
        return {i.name.lower() for i in items}

    def _get_hard_exclude(self, member) -> set:
        """Собирает запрещённые ингредиенты для участника."""
        exclude = set()
        user = member.user

        # Аллергии
        if isinstance(user.allergies, list):
            exclude.update(a.lower() for a in user.allergies)

        # Нелюбимые (если тариф позволяет)
        if self.features.get("disliked") and isinstance(user.disliked_products, list):
            exclude.update(d.lower() for d in user.disliked_products)

        # Аллергии всей семьи (Premium)
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
        except (TypeError, ValueError):
            return None

    def _fridge_score(self, recipe: Recipe, fridge_ids: set) -> int:
        """Количество ингредиентов рецепта, присутствующих в холодильнике."""
        if not fridge_ids:
            return 0
        score = 0
        for ing in recipe.ingredients:
            if ing.get("name", "").lower() in fridge_ids:
                score += 1
        return score

    def _pick_recipe(
        self,
        pool: List[Recipe],
        used: set,
        hard_exclude: set,
        fridge_ids: set,
        target_cal: Optional[int],
        meal_type: str,
    ) -> Optional[Recipe]:
        candidates = [r for r in pool if r.id not in used and self._recipe_passes_hard(r, hard_exclude)]

        if not candidates:
            # Смягчаем ограничение на повторы
            candidates = [r for r in pool if self._recipe_passes_hard(r, hard_exclude)]

        if not candidates:
            return None

        # Калорийный коридор ±200 ккал (мягкое)
        if target_cal:
            per_meal = target_cal / len(MEAL_TYPES)
            cal_ok = [r for r in candidates if (c := self._recipe_cal(r)) and abs(c - per_meal) <= 200]
            if cal_ok:
                candidates = cal_ok

        # Бонус за холодильник — сортируем по убыванию совпадений
        if fridge_ids:
            candidates.sort(key=lambda r: self._fridge_score(r, fridge_ids), reverse=True)
            # берём топ-10 и выбираем случайно из них
            candidates = candidates[:10]

        return random.choice(candidates)
