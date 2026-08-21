"""MG_SHELFLIFE: предполагаемый срок годности покупки.

Считаем от даты покупки: производства мы не знаем. Поэтому в справочнике лежит
не «срок по этикетке», а «сколько живёт после покупки» — поправка на уже
пролежавшее зашита в само число. Иначе пришлось бы вычитать из этикеточного
срока догадку о времени в пути, причём разную для молока и для крупы.

Дата, полученная здесь, — предположение, а не факт. Показывать её надо там, где
её видно и можно поправить до сохранения: молча проставленный неверный срок
рождает ложные «скоро испортится», а от них перестают читать и настоящие.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def shelf_life_days(product=None, category=None):
    """Срок хранения после покупки. None — подставлять нечего.

    Продукт важнее категории: ультрапастеризованное молоко живёт полгода, а
    категория «молочные» знает только про обычное.
    """
    if product is not None:
        own = getattr(product, "shelf_life_days", None)
        if own:
            return own
        category = category or getattr(product, "category_fk", None)
    days = getattr(category, "shelf_life_days", None) if category is not None else None
    return days or None


def suggest_expiry(product=None, category=None, purchased_on=None):
    """Предполагаемая дата «годен до». None — если срок неизвестен."""
    days = shelf_life_days(product=product, category=category)
    if not days:
        return None
    return (purchased_on or timezone.localdate()) + timedelta(days=days)


def suggest_for_shopping_item(item, purchased_on=None):
    """То же для позиции списка покупок: у неё бывает своя категория."""
    return suggest_expiry(
        product=getattr(item, "product", None),
        category=getattr(item, "category_fk", None),
        purchased_on=purchased_on,
    )
