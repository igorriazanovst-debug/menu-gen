#!/usr/bin/env python3
"""
Патч бэкенда:
1. generator.py — поддержка 3 или 5 приёмов пищи + правило салата
2. serializers.py — поле meal_plan_type
"""
import pathlib

ROOT = pathlib.Path("/opt/menugen/backend")

# ── generator.py ─────────────────────────────────────────────────────────────

GENERATOR = ROOT / "apps/menu/generator.py"

NEW_GENERATOR = '''\
import random
from datetime import date
from typing import List, Optional

from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe

MEAL_PLAN_3 = ["breakfast", "lunch", "dinner"]
MEAL_PLAN_5 = ["breakfast", "snack1", "lunch", "snack2", "dinner"]

# При сохранении в DB snack1/snack2 → "snack"
MEAL_TYPE_DB = {
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "snack1": "snack",
    "snack2": "snack",
}

# Категории, которые считаются "салатом / клетчаткой"
SALAD_CATEGORIES = {"салат", "salad", "овощное", "vegetables", "овощи", "клетчатка", "fiber", "зелень"}

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

    meal_plan_type: "3" (завтрак/обед/ужин) или "5" (завтрак/перекус/обед/перекус/ужин)
    Правило: каждый приём пищи сопровождается салатом/клетчаткой (отдельный recipe item).
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
        meal_plan = self.filters.get("meal_plan_type", "3")
        self.meal_types = MEAL_PLAN_5 if str(meal_plan) == "5" else MEAL_PLAN_3

    # ── public ────────────────────────────────────────────────────────────────

    def generate(self) -> List[dict]:
        """Возвращает список dict: member, meal_type, day_offset, recipe, is_salad."""
        pool = self._build_recipe_pool()
        salad_pool = self._build_salad_pool()
        fridge_ids = self._get_fridge_ingredient_names()
        items = []
        used_per_member: dict = {m.id: set() for m in self.members}

        for day in range(self.period_days):
            for member in self.members:
                target_cal = self._get_calorie_target(member)
                hard_exclude = self._get_hard_exclude(member)

                for meal_slot in self.meal_types:
                    db_meal_type = MEAL_TYPE_DB[meal_slot]

                    # основное блюдо
                    recipe = self._pick_recipe(
                        pool=pool,
                        used=used_per_member[member.id],
                        hard_exclude=hard_exclude,
                        fridge_ids=fridge_ids,
                        target_cal=target_cal,
                        meal_type=db_meal_type,
                        exclude_salad=True,
                    )
                    if recipe:
                        used_per_member[member.id].add(recipe.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "meal_slot": meal_slot,
                            "day_offset": day,
                            "recipe": recipe,
                            "is_salad": False,
                        })

                    # салат / клетчатка
                    salad = self._pick_salad(
                        pool=salad_pool,
                        used=used_per_member[member.id],
                        hard_exclude=hard_exclude,
                    )
                    if salad:
                        used_per_member[member.id].add(salad.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "meal_slot": meal_slot,
                            "day_offset": day,
                            "recipe": salad,
                            "is_salad": True,
                        })

        return items

    # ── private ───────────────────────────────────────────────────────────────

    def _build_recipe_pool(self) -> List[Recipe]:
        qs = Recipe.objects.filter(is_published=True)
        country = self.filters.get("country")
        if country and self.features.get("country"):
            qs = qs.filter(country__iexact=country)
        max_time = self.filters.get("max_cook_time")
        if max_time:
            qs = qs.exclude(cook_time="")
        recipes = list(qs.order_by("?")[:1000])
        if max_time:
            def _minutes(ct):
                try:
                    return int(str(ct).split()[0])
                except Exception:
                    return 9999
            recipes = [r for r in recipes if _minutes(r.cook_time) <= int(max_time)]
        return recipes[:500]

    def _build_salad_pool(self) -> List[Recipe]:
        """Пул салатов/клетчатки из всех опубликованных рецептов."""
        qs = Recipe.objects.filter(is_published=True)
        country = self.filters.get("country")
        if country and self.features.get("country"):
            qs = qs.filter(country__iexact=country)
        all_recipes = list(qs.order_by("?")[:1000])
        salads = [r for r in all_recipes if self._is_salad(r)]
        return salads if salads else []

    def _is_salad(self, recipe: Recipe) -> bool:
        cats = {c.lower() for c in (recipe.categories or [])}
        title_lower = recipe.title.lower()
        if cats & SALAD_CATEGORIES:
            return True
        if any(kw in title_lower for kw in ("салат", "salad", "овощной", "зелёный", "греческий", "цезарь")):
            return True
        return False

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
        except (TypeError, ValueError):
            return None

    def _fridge_score(self, recipe: Recipe, fridge_ids: set) -> int:
        if not fridge_ids:
            return 0
        return sum(1 for ing in recipe.ingredients if ing.get("name", "").lower() in fridge_ids)

    def _pick_recipe(
        self,
        pool: List[Recipe],
        used: set,
        hard_exclude: set,
        fridge_ids: set,
        target_cal: Optional[int],
        meal_type: str,
        exclude_salad: bool = False,
    ) -> Optional[Recipe]:
        candidates = [
            r for r in pool
            if r.id not in used and self._recipe_passes_hard(r, hard_exclude)
            and (not exclude_salad or not self._is_salad(r))
        ]
        if not candidates:
            candidates = [
                r for r in pool
                if self._recipe_passes_hard(r, hard_exclude)
                and (not exclude_salad or not self._is_salad(r))
            ]
        if not candidates:
            return None
        if target_cal:
            per_meal = target_cal / len(self.meal_types)
            cal_ok = [r for r in candidates if (c := self._recipe_cal(r)) and abs(c - per_meal) <= 200]
            if cal_ok:
                candidates = cal_ok
        if fridge_ids:
            candidates.sort(key=lambda r: self._fridge_score(r, fridge_ids), reverse=True)
            candidates = candidates[:10]
        return random.choice(candidates)

    def _pick_salad(
        self,
        pool: List[Recipe],
        used: set,
        hard_exclude: set,
    ) -> Optional[Recipe]:
        candidates = [
            r for r in pool
            if r.id not in used and self._recipe_passes_hard(r, hard_exclude)
        ]
        if not candidates:
            candidates = [r for r in pool if self._recipe_passes_hard(r, hard_exclude)]
        if not candidates:
            return None
        return random.choice(candidates)
'''

GENERATOR.write_text(NEW_GENERATOR, encoding="utf-8")
print(f"✓ {GENERATOR}")

# ── serializers.py — добавить поле meal_plan_type ────────────────────────────

SERIALIZERS = ROOT / "apps/menu/serializers.py"
src = SERIALIZERS.read_text(encoding="utf-8")

OLD = "    calorie_min = serializers.IntegerField(required=False, min_value=0)\n    calorie_max = serializers.IntegerField(required=False, min_value=0)"
NEW = "    calorie_min = serializers.IntegerField(required=False, min_value=0)\n    calorie_max = serializers.IntegerField(required=False, min_value=0)\n    meal_plan_type = serializers.ChoiceField(choices=['3', '5'], default='3', required=False)"

if "meal_plan_type" not in src:
    if OLD in src:
        src = src.replace(OLD, NEW)
        SERIALIZERS.write_text(src, encoding="utf-8")
        print(f"✓ {SERIALIZERS}")
    else:
        print(f"⚠ Не найден якорь в {SERIALIZERS}, проверь вручную")
else:
    print(f"  skip {SERIALIZERS} (meal_plan_type already exists)")

# ── views.py — передать meal_plan_type в filters ──────────────────────────────

VIEWS = ROOT / "apps/menu/views.py"
vsrc = VIEWS.read_text(encoding="utf-8")

OLD_V = "        if data.get('calorie_max'):\n            filters['calorie_max'] = data['calorie_max']"
NEW_V = "        if data.get('calorie_max'):\n            filters['calorie_max'] = data['calorie_max']\n        if data.get('meal_plan_type'):\n            filters['meal_plan_type'] = data['meal_plan_type']"

if "meal_plan_type" not in vsrc:
    if OLD_V in vsrc:
        vsrc = vsrc.replace(OLD_V, NEW_V)
        VIEWS.write_text(vsrc, encoding="utf-8")
        print(f"✓ {VIEWS}")
    else:
        # попробуем другой вариант
        OLD_V2 = "        if data.get(\"calorie_max\"):\n            filters[\"calorie_max\"] = data[\"calorie_max\"]"
        NEW_V2 = "        if data.get(\"calorie_max\"):\n            filters[\"calorie_max\"] = data[\"calorie_max\"]\n        if data.get(\"meal_plan_type\"):\n            filters[\"meal_plan_type\"] = data[\"meal_plan_type\"]"
        if OLD_V2 in vsrc:
            vsrc = vsrc.replace(OLD_V2, NEW_V2)
            VIEWS.write_text(vsrc, encoding="utf-8")
            print(f"✓ {VIEWS}")
        else:
            print(f"⚠ Не найден якорь в {VIEWS}, добавь meal_plan_type в filters вручную")
else:
    print(f"  skip {VIEWS} (meal_plan_type already exists)")

print("\nДонe. Перезапусти бэкенд:")
print("  cd /opt/menugen && docker compose restart backend")
