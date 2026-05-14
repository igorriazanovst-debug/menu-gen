# MG_604_V_tests: общие фикстуры для apps/recipes/tests
import pytest
from rest_framework.test import APIClient

from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def plain_user(db):
    return User.objects.create_user(
        email="plain@example.com",
        name="Обычный",
        password="x12345",
        user_type="user",
    )


@pytest.fixture
def author(db):
    return User.objects.create_user(
        email="author@example.com",
        name="Автор",
        password="x12345",
        user_type="recipe_author",
    )


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com",
        name="Админ",
        password="x12345",
        user_type="admin",
    )


@pytest.fixture
def recipe(db, author):
    return Recipe.objects.create(
        title="Базовый рецепт",
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "шаг 1"}],
        nutrition={"calories": {"value": "300"}},
        categories=["Завтраки"],
        author=author,
        is_published=True,
    )
