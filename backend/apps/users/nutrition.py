"""
Расчёт целевых КБЖУ по формулам Mifflin-St Jeor.

Алгоритм:
  1) BMR (базовый метаболизм) = Mifflin-St Jeor
  2) TDEE = BMR * activity_factor
  3) Целевые калории = TDEE +/- корректировка по цели
  4) Макросы:
     - белок: 1.6 г/кг при похудении/наборе, 1.2 г/кг при поддержании
     - жир:   0.8-1.0 г/кг (минимум 25% от калорий)
     - углеводы = остаток калорий
     - клетчатка: 14 г на 1000 ккал
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal


ACTIVITY_FACTOR = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}

# поправка к TDEE для цели (доля от TDEE)
GOAL_ADJUSTMENT = {
    "lose_weight": -0.20,   # дефицит 20%
    "maintain":     0.00,
    "gain_weight": +0.15,   # профицит 15%
    "healthy":      0.00,
}

# белок г/кг по цели
PROTEIN_PER_KG = {
    "lose_weight": 1.8,
    "maintain":    1.4,
    "gain_weight": 1.8,
    "healthy":     1.2,
}

# жир г/кг
FAT_PER_KG = {
    "lose_weight": 0.8,
    "maintain":    0.9,
    "gain_weight": 1.0,
    "healthy":     0.9,
}


def mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Базовый метаболизм (BMR) в ккал/день."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "male":
        return base + 5
    elif gender == "female":
        return base - 161
    # other -> среднее
    return base - 78


def tdee(bmr: float, activity_level: str) -> float:
    factor = ACTIVITY_FACTOR.get(activity_level, 1.55)
    return bmr * factor


def calorie_target_for_goal(tdee_value: float, goal: str) -> int:
    adj = GOAL_ADJUSTMENT.get(goal, 0.0)
    return int(round(tdee_value * (1 + adj)))


def macro_targets(calories: int, weight_kg: float, goal: str) -> dict:
    """Возвращает {protein_g, fat_g, carbs_g, fiber_g} в граммах."""
    protein_g = round(weight_kg * PROTEIN_PER_KG.get(goal, 1.4), 1)
    fat_g     = round(weight_kg * FAT_PER_KG.get(goal, 0.9), 1)

    # минимум жира: 20% от калорий
    fat_min_by_cal = round(calories * 0.20 / 9, 1)
    fat_g = max(fat_g, fat_min_by_cal)

    cal_protein = protein_g * 4
    cal_fat     = fat_g * 9
    cal_carbs   = max(0, calories - cal_protein - cal_fat)
    carbs_g     = round(cal_carbs / 4, 1)

    fiber_g = round(calories / 1000 * 14, 1)

    return {
        "protein_g": protein_g,
        "fat_g":     fat_g,
        "carbs_g":   carbs_g,
        "fiber_g":   fiber_g,
    }


def _age_from_birth_year(birth_year: int | None) -> int | None:
    if not birth_year:
        return None
    return date.today().year - birth_year


def calculate_targets(profile) -> dict | None:
    """
    На вход — Profile instance. Возвращает dict с целями или None,
    если данных недостаточно.

    {
      "calorie_target":   1850,
      "protein_target_g": 110.0,
      "fat_target_g":     65.0,
      "carbs_target_g":   180.0,
      "fiber_target_g":   25.0,
    }
    """
    if not profile.weight_kg or not profile.height_cm:
        return None
    age = _age_from_birth_year(profile.birth_year)
    if age is None:
        return None
    gender = profile.gender or "other"

    weight = float(profile.weight_kg)
    height = float(profile.height_cm)

    bmr = mifflin_st_jeor(weight, height, age, gender)
    tdee_val = tdee(bmr, profile.activity_level)
    cals = calorie_target_for_goal(tdee_val, profile.goal)
    macros = macro_targets(cals, weight, profile.goal)

    return {
        "calorie_target":   cals,
        "protein_target_g": Decimal(str(macros["protein_g"])),
        "fat_target_g":     Decimal(str(macros["fat_g"])),
        "carbs_target_g":   Decimal(str(macros["carbs_g"])),
        "fiber_target_g":   Decimal(str(macros["fiber_g"])),
    }


def fill_profile_targets(profile, force: bool = False) -> bool:
    """
    Заполняет цели в профиле. Не перезаписывает заданные пользователем
    значения (если force=False).

    Возвращает True если что-то изменилось.
    """
    targets = calculate_targets(profile)
    if not targets:
        return False

    changed = False
    for field, value in targets.items():
        current = getattr(profile, field, None)
        if force or current is None:
            if current != value:
                setattr(profile, field, value)
                changed = True
    return changed
