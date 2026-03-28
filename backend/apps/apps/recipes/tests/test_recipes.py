import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def author(db):
    user = User.objects.create_user(
        email="author@example.com", name="Автор", password="pass1234", user_type="recipe_author"
    )
    return user


@pytest.fixture
def plain_user(db):
    return User.objects.create_user(email="user@example.com", name="Юзер", password="pass1234")


@pytest.fixture
def recipe(db, author):
    return Recipe.objects.create(
        title="Тест рецепт",
        ingredients=[{"name": "Соль", "quantity": "1", "unit": "ч.л."}],
        steps=[{"text": "Посолить"}],
        nutrition={"calories": {"value": "100", "unit": "ккал"}},
        categories=["Супы"],
        is_custom=True,
        is_published=True,
        author=author,
    )


@pytest.mark.django_db
class TestRecipeList:
    def test_list_public(self, client, recipe):
        resp = client.get(reverse("recipe-list"))
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_search(self, client, recipe):
        resp = client.get(reverse("recipe-list"), {"search": "Тест"})
        assert resp.status_code == 200
        assert any("Тест" in r["title"] for r in resp.data["results"])

    def test_filter_by_category(self, client, recipe):
        resp = client.get(reverse("recipe-list"), {"category": "Супы"})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_no_results(self, client, recipe):
        resp = client.get(reverse("recipe-list"), {"category": "Несуществующая"})
        assert resp.status_code == 200
        assert resp.data["count"] == 0


@pytest.mark.django_db
class TestRecipeDetail:
    def test_detail_public(self, client, recipe):
        resp = client.get(reverse("recipe-detail", args=[recipe.id]))
        assert resp.status_code == 200
        assert resp.data["title"] == recipe.title
        assert "ingredients" in resp.data
        assert "steps" in resp.data

    def test_detail_not_found(self, client):
        resp = client.get(reverse("recipe-detail", args=[99999]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestRecipeCreate:
    def _payload(self):
        return {
            "title": "Новый рецепт",
            "cook_time": "30 мин",
            "servings": 4,
            "ingredients": [{"name": "Мука", "quantity": "200", "unit": "г"}],
            "steps": [{"text": "Смешать"}],
            "nutrition": {},
            "categories": ["Выпечка"],
        }

    def test_create_as_author(self, client, author):
        client.force_authenticate(author)
        resp = client.post(reverse("recipe-list"), self._payload(), format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Новый рецепт"

    def test_create_as_plain_user_forbidden(self, client, plain_user):
        client.force_authenticate(plain_user)
        resp = client.post(reverse("recipe-list"), self._payload(), format="json")
        assert resp.status_code == 403

    def test_create_unauthenticated(self, client):
        resp = client.post(reverse("recipe-list"), self._payload(), format="json")
        assert resp.status_code == 401

    def test_create_invalid_ingredients(self, client, author):
        client.force_authenticate(author)
        payload = self._payload()
        payload["ingredients"] = [{"no_name_field": "x"}]
        resp = client.post(reverse("recipe-list"), payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestRecipeUpdate:
    def test_update_by_author(self, client, author, recipe):
        client.force_authenticate(author)
        resp = client.patch(
            reverse("recipe-detail", args=[recipe.id]),
            {"title": "Обновлённый рецепт"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["title"] == "Обновлённый рецепт"

    def test_update_by_other_user_forbidden(self, client, plain_user, recipe):
        client.force_authenticate(plain_user)
        resp = client.patch(
            reverse("recipe-detail", args=[recipe.id]),
            {"title": "Чужое изменение"},
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestRecipeDelete:
    def test_delete_by_author(self, client, author, recipe):
        client.force_authenticate(author)
        resp = client.delete(reverse("recipe-detail", args=[recipe.id]))
        assert resp.status_code == 204

    def test_delete_by_other_user_forbidden(self, client, plain_user, recipe):
        client.force_authenticate(plain_user)
        resp = client.delete(reverse("recipe-detail", args=[recipe.id]))
        assert resp.status_code == 403
