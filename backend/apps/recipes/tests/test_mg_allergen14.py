"""MG_ALLERGEN14: классификатор аллергенов + автозаполнение Recipe.allergens
+ эндпоинт /users/allergens/."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.allergens import classify_ingredient_names, public_allergens, resolve_allergy
from apps.recipes.models import Recipe

User = get_user_model()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Сыр гауда", ["milk"]),
        ("Сырой картофель", []),
        ("Сырники из творога", ["milk"]),
        ("Пшеничная мука", ["gluten"]),
        ("Пшено (крупа)", []),
        ("Креветки", ["crustaceans"]),
        ("Кальмары", ["molluscs"]),
        ("Лосось", ["fish"]),
        ("Сельдерей", ["celery"]),
        ("Арахис", ["peanuts"]),
        ("Кунжут", ["sesame"]),
        ("Фундук", ["nuts"]),
        ("Кетчуп", []),
    ],
)
def test_classifier(name, expected):
    assert classify_ingredient_names([name]) == sorted(set(expected))


def test_resolve_allergy():
    assert resolve_allergy("milk") == "milk"
    assert resolve_allergy("Молоко") == "milk"
    assert resolve_allergy("сыр") == "milk"
    assert resolve_allergy("орех") == "nuts"
    assert resolve_allergy("какая-то фигня") is None


@pytest.mark.django_db
def test_recipe_save_autoclassifies():
    r = Recipe.objects.create(
        title="Сырный суп",
        ingredients=[
            {"name": "Сыр российский", "quantity": "100", "unit": "г"},
            {"name": "Пшеничная мука", "quantity": "20", "unit": "г"},
            {"name": "Картофель", "quantity": "2", "unit": "шт"},
        ],
    )
    assert set(r.allergens) == {"milk", "gluten"}


@pytest.mark.django_db
def test_allergen_endpoint_returns_14():
    user = User.objects.create_user(email="a@a.a", password="x", name="A")
    client = APIClient()
    client.force_authenticate(user)
    r = client.get(reverse("users-allergens"))
    assert r.status_code == 200, r.content
    rows = r.json()
    assert len(rows) == 14
    keys = {row["key"] for row in rows}
    assert {"milk", "gluten", "fish", "peanuts", "sesame"} <= keys
    assert all({"key", "label", "full", "group"} <= set(row) for row in rows)
    # список публичный и совпадает с модулем
    assert [row["key"] for row in rows] == [a["key"] for a in public_allergens()]
