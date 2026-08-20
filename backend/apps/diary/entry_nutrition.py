"""КБЖУ одной записи дневника.

Вынесено из views, чтобы считать одинаково везде: у кабинета специалиста та же
задача, а своя арифметика поверх `nutrition` даёт нули на первом же поле с
другим именем («protein» вместо «proteins») и падает на записях, где значение
лежит словарём.
"""

# MG_605D: ключи КБЖУ в JSON-поле nutrition.
NUTRITION_KEYS = ("calories", "proteins", "fats", "carbs")


def entry_nutrition(entry):
    """{calories, proteins, fats, carbs} для записи, с учётом quantity.

    Безопасно к битым и частичным данным: значение может быть числом, строкой
    или устаревшим словарём {"value": ...}.
    """
    nutr = entry.nutrition or {}
    try:
        qty = float(entry.quantity or 1)
    except (TypeError, ValueError):
        qty = 1.0
    out = {}
    for key in NUTRITION_KEYS:
        raw = nutr.get(key)
        try:
            if isinstance(raw, dict):
                val = float(raw.get("value", 0) or 0)
            elif raw is None:
                val = 0.0
            else:
                val = float(raw)
            out[key] = val * qty
        except (TypeError, ValueError, AttributeError):
            out[key] = 0.0
    return out


def empty_bucket():
    return {k: 0.0 for k in NUTRITION_KEYS}


def add_bucket(dst, src):
    for k in NUTRITION_KEYS:
        dst[k] += src[k]
