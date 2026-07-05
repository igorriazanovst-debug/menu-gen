"""MG_ALLERGEN: canonical_allergen() — схлопывание вариантов к базовому слову."""

import pytest

from apps.fridge.aliases import canonical_allergen


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Сыр гауда", "сыр"),
        ("Сыр тёртый", "сыр"),
        ("Сыр российский", "сыр"),
        ("Молоко 2.5%", "молоко"),
        ("Творог 5%", "творог"),
        ("Йогурт греческий", "йогурт"),
        # первое слово-«пустышка» пропускается ради содержательного
        ("Филе куриное", "куриное"),
        ("Масло оливковое", "оливковое"),
        # одиночные слова остаются собой
        ("Пармезан", "пармезан"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_canonical_allergen(name, expected):
    assert canonical_allergen(name) == expected


def test_generator_canon_allergens_static():
    # Генератор схлопывает список аллергенов к базам (staticmethod, без БД).
    from apps.menu.generator import MenuGenerator

    out = MenuGenerator._canon_allergens(["Сыр гауда", "Сыр тёртый", "молоко", 123, None])
    assert out == {"сыр", "молоко"}
