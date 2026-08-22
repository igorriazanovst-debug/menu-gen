"""MG_BARCODEDB: сопоставление штрих-кода с записью в базе.

Один и тот же товар приходит к нам в разных написаниях кода. На упаковке
американского соуса напечатан UPC-A из 12 цифр, в выгрузке сети он же лежит
как GTIN-13 с ведущим нулём, а сканер в телефоне вернёт то, что увидит.
Строгое сравнение строк на этом промахивается: товар в базе есть, а поиск
говорит «не найден» — и мы идём выдумывать его заново.

Поэтому сравниваем по канонической форме — 13 цифр с ведущими нулями, — но
храним код как есть: в базе уже лежат записи, добытые сканером, и переписывать
их ради красоты незачем.
"""

from __future__ import annotations

from django.db.models import Q

CANONICAL_LENGTH = 13


def normalize(code) -> str:
    """Только цифры, дополненные слева нулями до 13. Пусто — если цифр нет."""
    digits = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not digits:
        return ""
    return digits.zfill(CANONICAL_LENGTH) if len(digits) < CANONICAL_LENGTH else digits


def variants(code) -> list[str]:
    """Написания одного кода, которые могли попасть в базу.

    Сам код, он же без ведущих нулей и он же дополненный до 13 — этого хватает,
    чтобы UPC-A с упаковки нашёл запись, заведённую как GTIN-13, и наоборот.
    """
    raw = str(code or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    out = []
    for candidate in (raw, digits, digits.lstrip("0"), normalize(digits)):
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def lookup_q(code):
    """Условие для поиска продукта по штрих-коду во всех его написаниях."""
    return Q(barcode__in=variants(code))
