"""MG_PACKSIZE: граммы из строки фасовки — «250 г», «930 мл», «4.5 г x 4 шт».

Справочники сетей и OpenFoodFacts приносят фасовку строкой, и импорт кладёт её
в `Product.default_unit` (см. `import_barcode_catalog.py`). Для десятков тысяч
товаров вес упаковки, таким образом, уже лежит в базе — его не надо ни
выдумывать, ни спрашивать у модели, достаточно прочитать.

Тот же разбор давно работает в вебе (`utils/packageSize.ts`, MG_DIARYSCAN): там
он подставляет в дневник целую пачку. Здесь — вторая половина той же задачи, и
поэтому правила совпадают дословно, вплоть до кириллической «х» в множителе.
Расхождение между двумя реализациями было бы невидимым: обе молча возвращают
None, когда не разобрали, и никто бы не заметил, что они разошлись.

Миллилитры считаем граммами. Для напитков разница в пределах процентов, а
alternativa — заставить человека пересчитывать плотность самому.
"""

import re
from decimal import Decimal

_MULTIPLIERS = {
    "г": Decimal(1),
    "гр": Decimal(1),
    "g": Decimal(1),
    "мл": Decimal(1),
    "ml": Decimal(1),
    "кг": Decimal(1000),
    "kg": Decimal(1000),
    "л": Decimal(1000),
    "l": Decimal(1000),
}

# Единица не должна продолжаться буквой: иначе «л» поймается в «лоток», а «г» —
# в «говядина».
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(кг|kg|мл|ml|гр|г|g|л|l)(?![а-яёa-z])", re.IGNORECASE)

# «4.5 г x 4 шт» — пачка из четырёх пакетиков. На этикетках кириллическую «х» и
# латинскую «x» не различают, поэтому принимаем обе, плюс «×» и «*».
_PACKS_RE = re.compile(r"^\s*[xх×*]\s*(\d+)", re.IGNORECASE)

# Сверху — здравый смысл: двадцать килограммов в одной упаковке холодильника не
# бывает, это разобранная не та часть строки. Снизу — ноль и отрицательные.
_MAX_GRAMS = Decimal(20000)


def package_grams(text):
    """Граммы из строки фасовки. None — если размер не читается («упак», «шт»).

    Возвращать None здесь честнее, чем угадывать: неверный вес не виден никому
    и тихо списывает из холодильника не то количество.
    """
    raw = str(text or "").strip().lower().replace(",", ".")
    if not raw:
        return None

    match = _SIZE_RE.search(raw)
    if not match:
        return None

    try:
        amount = Decimal(match.group(1)) * _MULTIPLIERS[match.group(2).lower()]
    except (ArithmeticError, KeyError, ValueError):
        return None

    packs = _PACKS_RE.match(raw[match.end() :])
    if packs:
        amount *= Decimal(packs.group(1))

    if amount <= 0 or amount > _MAX_GRAMS:
        return None
    return amount
