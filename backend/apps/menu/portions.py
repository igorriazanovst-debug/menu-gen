"""
MG-304: расчёт суточной нормы овощей+фруктов в граммах per member и веса
порции конкретного рецепта.

Цель — гарантировать, что в дневном меню каждого члена семьи присутствует
эквивалент 5 порций овощей/фруктов (для взрослого 1 порция ≈ 150 г → 750 г/сутки),
скорректированный по возрасту плавной формулой.

Источник веса порции рецепта (приоритеты, fallback вниз):
  1) Recipe.nutrition.weight.value  (граммы на 1 порцию)
  2) Recipe.povar_raw.dish_weight_g_calc / servings_normalized (или servings)
  3) DEFAULT_PORTION_G_FALLBACK = 200 г (страховка для редких пустых)
"""
# MG_304_V_portions
from __future__ import annotations
from datetime import date
from typing import Optional

ADULT_PORTION_G       = 150.0
PORTIONS_PER_DAY      = 5
DEFAULT_PORTION_G_FALLBACK = 200.0

# плавная коррекция нормы по возрасту (множитель к ADULT_PORTION_G * 5)
# < 4 года   → 0.40
# 4..6       → 0.55
# 7..10      → 0.70
# 11..13     → 0.85
# >=14       → 1.00 (взрослая норма)
def _age_multiplier(age: Optional[int]) -> float:
    if age is None:
        return 1.0
    if age < 0:
        return 1.0
    if age < 4:
        return 0.40
    if age < 7:
        return 0.55
    if age < 11:
        return 0.70
    if age < 14:
        return 0.85
    return 1.00


def _member_age(member, ref_date: Optional[date] = None) -> Optional[int]:
    """Возраст члена семьи на ref_date по profile.birth_year. None если нет данных."""
    try:
        profile = getattr(member.user, "profile", None)
        by = getattr(profile, "birth_year", None)
        if not by:
            return None
        ref = ref_date or date.today()
        return max(0, ref.year - int(by))
    except Exception:
        return None


def daily_target_grams(member, ref_date: Optional[date] = None) -> float:
    """Целевая суточная граммовка овощей+фруктов для члена семьи (гр)."""
    age = _member_age(member, ref_date)
    return ADULT_PORTION_G * PORTIONS_PER_DAY * _age_multiplier(age)


def recipe_portion_grams(recipe) -> float:
    """
    Вес 1 порции рецепта в граммах.
    Приоритеты: nutrition.weight.value → povar_raw.dish_weight_g_calc / servings → fallback.
    """
    # 1) nutrition.weight.value
    try:
        nut = recipe.nutrition or {}
        w = nut.get("weight") if isinstance(nut, dict) else None
        if isinstance(w, dict):
            v = w.get("value")
        else:
            v = w
        if v not in (None, "", 0, "0"):
            g = float(str(v).replace(",", "."))
            if g > 0:
                return g
    except Exception:
        pass

    # 2) povar_raw.dish_weight_g_calc / servings_normalized (или servings)
    try:
        pr = getattr(recipe, "povar_raw", None) or {}
        dw = pr.get("dish_weight_g_calc")
        sn = getattr(recipe, "servings_normalized", None) or getattr(recipe, "servings", None) or 1
        if dw and sn:
            g = float(dw) / float(sn)
            if g > 0:
                return g
    except Exception:
        pass

    return DEFAULT_PORTION_G_FALLBACK
