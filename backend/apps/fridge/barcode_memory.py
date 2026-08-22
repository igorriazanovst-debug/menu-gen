"""MG_FAMBARCODE: память семьи о своих штрих-кодах.

Справочник сети знает её ассортимент, OpenFoodFacts — то, что попало в открытую
базу. Всё остальное человек вбивал руками каждый раз заново: код нигде не
оставался, и та же упаковка завтра снова «не найдена».

Память семьи идёт первой, даже впереди справочника. Это не только про
неизвестные товары: если в справочнике товар записан неудачно — не той марки,
не того объёма, — исправление, сделанное однажды, должно держаться, а не
перебиваться выгрузкой при каждом скане.
"""

from __future__ import annotations

from .barcodes import normalize


def remember(family, barcode, name, unit=None, category=None, user=None):
    """Запомнить «этот код у этой семьи — вот это». None — если нечего помнить."""
    from .models import FamilyBarcode

    code, name = normalize(barcode), (name or "").strip()
    if family is None or not code or not name:
        return None

    entry, _ = FamilyBarcode.objects.update_or_create(
        family=family,
        barcode=code,
        defaults={
            "name": name[:255],
            "unit": (unit or "")[:50],
            "category_fk": category,
            "created_by": user if user and user.is_authenticated else None,
        },
    )
    return entry


def recall(family, barcode):
    """Что эта семья помнит про код. None — если ничего."""
    from .models import FamilyBarcode

    code = normalize(barcode)
    if family is None or not code:
        return None
    return FamilyBarcode.objects.filter(family=family, barcode=code).select_related("category_fk").first()
