"""
Расчёт целевых КБЖУ по формулам Mifflin-St Jeor (MG-202).

Алгоритм:
  1) BMR (базовый метаболизм) = Mifflin-St Jeor
        male:   10*w + 6.25*h - 5*age + 5
        female: 10*w + 6.25*h - 5*age - 161
        other:  10*w + 6.25*h - 5*age - 78  (среднее)
  2) TDEE = BMR * activity_factor
  3) Целевые калории по цели:
        lose_weight: TDEE - 500
        gain_weight: TDEE + 300
        maintain / healthy: TDEE
  4) Макросы:
        белок:    1.5 г/кг веса
        жир:      30% калорий / 9
        углеводы: (calories - белки*4 - жиры*9) / 4
        клетчатка: 14 г / 1000 ккал
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

MG_202_V = 1   # маркер версии формулы (для идемпотентности apply-скрипта)
MG_205_V = 1   # учёт источника правок (auto/user/specialist)

ACTIVITY_FACTOR = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}

GOAL_DELTA_KCAL = {
    "lose_weight": -500,
    "gain_weight": +300,
    "maintain":       0,
    "healthy":        0,
}

PROTEIN_PER_KG = 1.5
FAT_PCT_OF_CAL = 0.30
FIBER_PER_1000_KCAL = 14


def mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "male":
        return base + 5
    if gender == "female":
        return base - 161
    return base - 78


def tdee(bmr: float, activity_level: str) -> float:
    return bmr * ACTIVITY_FACTOR.get(activity_level, 1.55)


def calorie_target_for_goal(tdee_value: float, goal: str) -> int:
    delta = GOAL_DELTA_KCAL.get(goal, 0)
    return int(round(tdee_value + delta))


def macro_targets(calories: int, weight_kg: float) -> dict:
    """{protein_g, fat_g, carbs_g, fiber_g} по формуле MG-202."""
    protein_g = round(weight_kg * PROTEIN_PER_KG, 1)
    fat_g     = round((calories * FAT_PCT_OF_CAL) / 9, 1)
    cal_protein = protein_g * 4
    cal_fat     = fat_g * 9
    cal_carbs   = max(0, calories - cal_protein - cal_fat)
    carbs_g     = round(cal_carbs / 4, 1)
    fiber_g     = round(calories / 1000 * FIBER_PER_1000_KCAL, 1)
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
    """
    if not profile.weight_kg or not profile.height_cm:
        return None
    age = _age_from_birth_year(profile.birth_year)
    if age is None:
        return None
    gender = (profile.gender or "other").lower()

    weight = float(profile.weight_kg)
    height = float(profile.height_cm)

    bmr      = mifflin_st_jeor(weight, height, age, gender)
    tdee_val = tdee(bmr, (profile.activity_level or "moderate"))
    cals     = calorie_target_for_goal(tdee_val, (profile.goal or "maintain"))
    macros   = macro_targets(cals, weight)

    return {
        "calorie_target":   cals,
        "protein_target_g": Decimal(str(macros["protein_g"])),
        "fat_target_g":     Decimal(str(macros["fat_g"])),
        "carb_target_g":    Decimal(str(macros["carbs_g"])),
        "fiber_target_g":   Decimal(str(macros["fiber_g"])),
    }


def fill_profile_targets(profile, force: bool = False, actor=None) -> bool:
    """
    Заполняет цели в профиле по формуле Mifflin-St Jeor.

    MG-205: учитывает источник последней правки (ProfileTargetAudit).
      - force=False: НЕ перетирает поля, у которых last source in {'user','specialist'}
      - force=True : перетирает всегда; ставит source='auto'
    Каждое реальное изменение пишется в ProfileTargetAudit (+AuditLog) через audit.record_target_change.

    actor — User, инициатор force-сброса (например, диетолог через "Сбросить к авто").
    Для обычного авторасчёта actor=None.

    Возвращает True если что-то изменилось.
    """
    from .audit import record_target_change, is_locked

    targets = calculate_targets(profile)
    if not targets:
        return False

    changed = False
    # Если профиль ещё не сохранён (pk is None) — записывать аудит нельзя (FK requires pk).
    # В этом случае просто проставляем поля; аудит запишем после save() через post_save-хук
    # (см. apps/users/models.Profile.save).
    has_pk = profile.pk is not None

    for field, value in targets.items():
        current = getattr(profile, field, None)
        # MG-205: проверяем lock для существующего профиля
        if has_pk and not force and is_locked(profile, field):
            continue
        # Для нового профиля (без pk) lock проверять негде — записей ещё нет.
        if force or current is None:
            if current != value:
                setattr(profile, field, value)
                changed = True
                if has_pk:
                    record_target_change(
                        profile=profile,
                        field=field,
                        new_value=value,
                        source="auto",
                        by_user=actor,
                        old_value=current,
                        reason="auto-recalc (force)" if force else "auto-fill (was empty)",
                    )
    return changed
