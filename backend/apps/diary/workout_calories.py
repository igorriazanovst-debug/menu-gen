"""MG_WORKOUT: сколько калорий потрачено на занятии.

Формула общепринятая: `MET × 3,5 × вес(кг) × минуты / 200`. Числа в ней не
подгоночные — 3,5 мл кислорода на килограмм в минуту это определение одного
MET, а деление на 200 переводит литры кислорода в килокалории.

Два правила, которые важнее самой формулы.

**Без веса расход не считается.** Вес входит в формулу множителем, и подставить
вместо него «среднего человека» значит ошибиться на четверть в любую сторону.
Пусто — значит человек впишет калории сам, и это честнее выдуманного числа.

**Посчитанное сохраняется числом, а не пересчитывается при показе.** Вес
меняется; пересчёт задним числом переписал бы историю, и вчерашняя пробежка
«подешевела» бы оттого, что сегодня человек похудел.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

# Определение MET: 3,5 мл кислорода на кг в минуту. Делитель 200 переводит
# потреблённый кислород в килокалории.
_ML_O2_PER_KG_MIN = Decimal("3.5")
_ML_O2_TO_KCAL = Decimal("200")

# Выше этого за одно занятие — почти наверняка опечатка в минутах: столько
# не тратит и марафонец. Молчаливо сохранить такое значит испортить сводку дня.
MAX_WORKOUT_KCAL = 5000


def burned_kcal(met, weight_kg, duration_min) -> Optional[int]:
    """Расход за занятие в килокалориях. None — посчитать не из чего.

    Возвращает целое: доли килокалории в дневнике не значат ничего, а
    создают вид точности, которой нет — сама формула даёт разброс в проценты.
    """
    if not met or not weight_kg or not duration_min:
        return None
    try:
        value = (
            Decimal(str(met)) * _ML_O2_PER_KG_MIN * Decimal(str(weight_kg)) * Decimal(str(duration_min))
        ) / _ML_O2_TO_KCAL
    except (TypeError, ValueError, ArithmeticError):
        return None
    if value <= 0:
        return None
    rounded = int(value.to_integral_value())
    return min(rounded, MAX_WORKOUT_KCAL)


def latest_weight_kg(user) -> Optional[Decimal]:
    """Последний известный вес человека: замер из дневника, иначе профиль.

    Замер важнее профиля: в профиле вес перезаписывается и может быть
    годовалым, а в дневнике — точка с датой. Если нет ни того, ни другого,
    считать нечем, и это не ошибка — просто калории введут руками.
    """
    from .models import WeightLog

    last = WeightLog.objects.filter(user=user).order_by("-date").values_list("weight_kg", flat=True).first()
    if last is not None:
        return last
    profile = getattr(user, "profile", None)
    return getattr(profile, "weight_kg", None) if profile else None
