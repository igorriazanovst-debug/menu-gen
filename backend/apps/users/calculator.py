"""
MG_206_V_calculator = 1

KBJU calculator: системы расчёта + пресеты диет + custom mode.

Используется в endpoints:
  POST /users/me/calculator/preview/ — расчёт без сохранения
  POST /users/me/calculator/apply/   — расчёт + сохранение в Profile + аудит

Системы:
  - mifflin           : Mifflin-St Jeor
  - harris_benedict   : Harris-Benedict revised
  - rospotrebnadzor   : Роспотребнадзор МР 2.3.1.0253-21 (формула = Mifflin-St Jeor)
  - efsa              : EFSA EU (формула = Mifflin-St Jeor)
  - custom            : пользователь вводит вручную

Пресеты диет (применяются ко всем не-custom системам):
  - balanced     : Б 20% / Ж 30% / У 50%
  - high_protein : Б 35% / Ж 25% / У 40%
  - low_carb     : Б 30% / Ж 45% / У 25%

Activity factors:
  sedentary 1.2 / light 1.375 / moderate 1.55 / active 1.725 / very_active 1.9

Goal deltas:
  lose_weight -500 / maintain 0 / gain_weight +300 / healthy 0
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

MG_206_V = 1

# ─── Configuration tables ───────────────────────────────────────────────────

SYSTEMS = {
    "mifflin": {
        "name": "Mifflin-St Jeor",
        "bmr_formula": "mifflin",
    },
    "harris_benedict": {
        "name": "Harris-Benedict (revised)",
        "bmr_formula": "harris_benedict",
    },
    "rospotrebnadzor": {
        "name": "Роспотребнадзор (МР 2.3.1.0253-21)",
        "bmr_formula": "mifflin",
    },
    "efsa": {
        "name": "EFSA (EU)",
        "bmr_formula": "mifflin",
    },
    "custom": {
        "name": "Свои значения",
        "bmr_formula": None,
    },
}

DIET_PRESETS = {
    "balanced": {"name": "Сбалансированный", "p": 0.20, "f": 0.30, "c": 0.50},
    "high_protein": {"name": "Высокобелковый", "p": 0.35, "f": 0.25, "c": 0.40},
    "low_carb": {"name": "Низкоуглеводный", "p": 0.30, "f": 0.45, "c": 0.25},
}

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_DELTAS = {
    "lose_weight": -500,
    "maintain": 0,
    "gain_weight": +300,
    "healthy": 0,
}

FIBER_PER_1000_KCAL = 14

VALID_GENDERS = ("male", "female", "other")
VALID_GOALS = tuple(GOAL_DELTAS.keys())
VALID_ACTIVITIES = tuple(ACTIVITY_FACTORS.keys())
VALID_SYSTEMS = tuple(SYSTEMS.keys())
VALID_DIETS = tuple(DIET_PRESETS.keys())
VALID_CUSTOM_MODES = ("grams", "percents")


# ─── BMR formulas ───────────────────────────────────────────────────────────


def bmr_mifflin(weight: float, height: float, age: int, gender: str) -> float:
    base = 10.0 * weight + 6.25 * height - 5.0 * age
    if gender == "male":
        return base + 5
    if gender == "female":
        return base - 161
    return base - 78  # other = average


def bmr_harris_benedict(weight: float, height: float, age: int, gender: str) -> float:
    male = 88.362 + 13.397 * weight + 4.799 * height - 5.677 * age
    female = 447.593 + 9.247 * weight + 3.098 * height - 4.330 * age
    if gender == "male":
        return male
    if gender == "female":
        return female
    return (male + female) / 2.0  # other = average


def compute_bmr(system: str, weight: float, height: float, age: int, gender: str) -> float:
    sys_def = SYSTEMS.get(system)
    if not sys_def:
        raise ValueError(f"Unknown system: {system}")
    f = sys_def.get("bmr_formula")
    if f == "mifflin":
        return bmr_mifflin(weight, height, age, gender)
    if f == "harris_benedict":
        return bmr_harris_benedict(weight, height, age, gender)
    raise ValueError(f"System {system} has no BMR formula (use custom flow)")


def age_from_birth_year(birth_year: int | None, ref_date: date | None = None) -> int | None:
    if not birth_year:
        return None
    ref = ref_date or date.today()
    return ref.year - int(birth_year)


# ─── Result helpers ─────────────────────────────────────────────────────────


def _round1(x: float) -> Decimal:
    return Decimal(f"{round(float(x), 1):.1f}")


def _macros_from_pcts(calories: int, p_pct: float, f_pct: float, c_pct: float) -> dict:
    """% уже как доли (0.20 / 0.30 / 0.50). Сумма должна быть ~1.0."""
    protein_g = round((calories * p_pct) / 4.0, 1)
    fat_g = round((calories * f_pct) / 9.0, 1)
    carb_g = round((calories * c_pct) / 4.0, 1)
    return {"protein_g": protein_g, "fat_g": fat_g, "carb_g": carb_g}


def _fiber_default(calories: int) -> float:
    return round(calories / 1000.0 * FIBER_PER_1000_KCAL, 1)


# ─── Main entrypoints ───────────────────────────────────────────────────────


def calculate_preset(data: dict) -> dict:
    """
    data = {
        system, diet, weight_kg, height_cm, birth_year, gender,
        activity_level, goal
    }
    Возвращает: dict с полями bmr, tdee, calorie_target, protein_target_g,
    fat_target_g, carb_target_g, fiber_target_g, age, system, diet.
    """
    system = data["system"]
    diet_code = data["diet"]
    weight = float(data["weight_kg"])
    height = float(data["height_cm"])
    age = age_from_birth_year(int(data["birth_year"]))
    if age is None:
        raise ValueError("birth_year required")
    gender = data.get("gender") or "other"
    activity = data.get("activity_level") or "moderate"
    goal = data.get("goal") or "maintain"

    diet = DIET_PRESETS[diet_code]
    bmr = compute_bmr(system, weight, height, age, gender)
    tdee_val = bmr * ACTIVITY_FACTORS.get(activity, 1.55)
    calories = int(round(tdee_val + GOAL_DELTAS.get(goal, 0)))
    macros = _macros_from_pcts(calories, diet["p"], diet["f"], diet["c"])
    fiber = _fiber_default(calories)

    return {
        "system": system,
        "diet": diet_code,
        "age": age,
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee_val)),
        "calorie_target": calories,
        "protein_target_g": _round1(macros["protein_g"]),
        "fat_target_g": _round1(macros["fat_g"]),
        "carb_target_g": _round1(macros["carb_g"]),
        "fiber_target_g": _round1(fiber),
    }


def calculate_custom_grams(data: dict) -> dict:
    """
    Прямой ввод абсолютных значений.
    data = {
        custom_calorie_target, custom_protein_g, custom_fat_g,
        custom_carb_g, custom_fiber_g
    }
    """
    cals = int(data["custom_calorie_target"])
    prot = float(data["custom_protein_g"])
    fat = float(data["custom_fat_g"])
    carb = float(data["custom_carb_g"])
    fiber = float(data["custom_fiber_g"])
    return {
        "system": "custom",
        "diet": None,
        "age": age_from_birth_year(data.get("birth_year")),
        "bmr": None,
        "tdee": None,
        "calorie_target": cals,
        "protein_target_g": _round1(prot),
        "fat_target_g": _round1(fat),
        "carb_target_g": _round1(carb),
        "fiber_target_g": _round1(fiber),
    }


def calculate_custom_percents(data: dict) -> dict:
    """
    Расчёт TDEE по Mifflin (универсальная формула BMR), затем дельта + %.
    data = {
        weight_kg, height_cm, birth_year, gender, activity_level,
        custom_calorie_delta, custom_protein_pct, custom_fat_pct,
        custom_carb_pct, custom_fiber_g
    }
    """
    weight = float(data["weight_kg"])
    height = float(data["height_cm"])
    age = age_from_birth_year(int(data["birth_year"]))
    if age is None:
        raise ValueError("birth_year required")
    gender = data.get("gender") or "other"
    activity = data.get("activity_level") or "moderate"

    bmr = bmr_mifflin(weight, height, age, gender)
    tdee_val = bmr * ACTIVITY_FACTORS.get(activity, 1.55)
    delta = int(data.get("custom_calorie_delta") or 0)
    calories = int(round(tdee_val + delta))

    p_pct = float(data["custom_protein_pct"]) / 100.0
    f_pct = float(data["custom_fat_pct"]) / 100.0
    c_pct = float(data["custom_carb_pct"]) / 100.0
    fiber = float(data.get("custom_fiber_g") or _fiber_default(calories))

    macros = _macros_from_pcts(calories, p_pct, f_pct, c_pct)
    return {
        "system": "custom",
        "diet": None,
        "age": age,
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee_val)),
        "calorie_target": calories,
        "protein_target_g": _round1(macros["protein_g"]),
        "fat_target_g": _round1(macros["fat_g"]),
        "carb_target_g": _round1(macros["carb_g"]),
        "fiber_target_g": _round1(fiber),
    }


def calculate(data: dict) -> dict:
    """Главный entrypoint. Маршрутизация по system / custom_mode."""
    system = data.get("system")
    if system not in VALID_SYSTEMS:
        raise ValueError(f"system must be one of {VALID_SYSTEMS}")
    if system == "custom":
        mode = data.get("custom_mode")
        if mode == "grams":
            return calculate_custom_grams(data)
        if mode == "percents":
            return calculate_custom_percents(data)
        raise ValueError("custom_mode required for custom system")
    return calculate_preset(data)
