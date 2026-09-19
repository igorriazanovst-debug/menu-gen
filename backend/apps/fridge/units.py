"""MG_UNITNORM: приведение единиц к граммам по товару.

Холодильник и рецепт говорят на разных языках. Холодильник — на языке магазина:
яйца в штуках, творог в упаковках, молоко в литрах. Рецепт — на языке кухни, в
граммах. Пока переводчика не было, эти две правды просто не встречались:
потребность «Яйца куриные 50 г» не находила в холодильнике «яйца 30 шт», хотя
товар определялся верно (#41, синоним отрабатывал). Списание это показало, но
болело не оно: список покупок вычитает холодильник тем же кодом, и яйца в него
попадали как «не лежат дома», сколько бы их ни лежало.

Переводчик здесь один и работает на оба конца — и на сборку списка покупок
(`_subtract_fridge`), и на списание при «приготовил» (`writeoff`). Если бы их
было два, они бы разошлись на первом же особом случае, и разницу никто бы не
заметил: оба места молчат, когда не сходится.

Чего нет в справочнике — то не переводится и ведёт себя как раньше: не
сходится. Это сознательно. Средний вес «по категории» или догадка по названию
не видны никому: человек получит не ту цифру в остатке и узнает об этом, только
открыв холодильник. Честная нехватка — меньшее зло.
"""

from decimal import Decimal, InvalidOperation


def norm_unit(unit):
    """Единица в каноничном виде: «шт.» → «шт», «уп» → «упаковка».

    Таблица синонимов одна на проект и живёт в сборке списка покупок — там она
    появилась и там же правится. Дублировать её здесь нельзя: две таблицы
    разойдутся, и «шт.» начнёт значить разное в разных местах.
    """
    from apps.shopping.services import _mg_norm_unit

    return _mg_norm_unit(unit)


def unit_weight_index(product_ids=None):
    """{(product_id, единица): граммов в одной единице}.

    Одним запросом на всё: у недельного меню под сотню позиций, и поштучные
    обращения к базе превратили бы сборку списка в сотню запросов.
    """
    from apps.fridge.models import ProductUnitWeight

    qs = ProductUnitWeight.objects.all()
    if product_ids is not None:
        ids = [pid for pid in product_ids if pid]
        if not ids:
            return {}
        qs = qs.filter(product_id__in=ids)
    return {(row.product_id, row.unit): row.grams for row in qs.only("product_id", "unit", "grams")}


def grams_per_unit(product_id, unit, index=None):
    """Сколько граммов в одной единице этого товара. None — неизвестно.

    Граммы и килограммы переводятся без всякого справочника: это не свойство
    товара, а арифметика. Справочник нужен там, где единица ничего не говорит
    о массе сама по себе.
    """
    from apps.shopping.services import _mg_unit_tables

    u = norm_unit(unit)
    if not u:
        return None
    mass, _vol, _clove = _mg_unit_tables()
    if u in mass:
        return mass[u]
    if not product_id:
        return None
    if index is None:
        index = unit_weight_index([product_id])
    return index.get((product_id, u))


def to_grams(quantity, unit, product_id, index=None):
    """Количество в граммах, или None, если перевести нечем."""
    if quantity is None:
        return None
    try:
        qty = quantity if isinstance(quantity, Decimal) else Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError):
        return None
    per = grams_per_unit(product_id, unit, index)
    if per is None:
        return None
    return qty * per


def from_grams(grams, unit, product_id, index=None):
    """Обратно: сколько это в единице `unit`. None — перевести нечем.

    Нужно там, где число возвращается человеку или в холодильник: списали
    граммами, а в позиции лежат штуки, и записать в неё надо штуки — иначе
    отмена вернёт не то.
    """
    per = grams_per_unit(product_id, unit, index)
    if per is None or per == 0 or grams is None:
        return None
    return grams / per
