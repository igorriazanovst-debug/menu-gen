# MG_604_V_tests
"""
MG-604: покрытие двух views в apps/recipes/views.py.

Missing lines:
  24-33   RecipeCountryListView.get (целиком)
  141-145 RecipeAuthorApplyView.perform_create (duplicate check + save)
"""
import pytest
from django.urls import reverse

from apps.recipes.models import Recipe, RecipeAuthor


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ RecipeCountryListView                                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestRecipeCountryList:
    def test_empty_returns_empty_list(self, client):
        resp = client.get(reverse("recipe-countries"))
        assert resp.status_code == 200
        assert resp.data == []

    def test_returns_distinct_sorted_countries(self, client, db, author):
        for c in ["Россия", "Италия", "Россия", "Грузия"]:
            Recipe.objects.create(
                title=f"Рец {c}",
                ingredients=[{"name": "и"}],
                steps=[{"text": "ш"}],
                country=c,
                is_published=True,
                author=author,
            )
        resp = client.get(reverse("recipe-countries"))
        assert resp.status_code == 200
        # отсортированы, без дубликатов
        assert resp.data == sorted({"Россия", "Италия", "Грузия"})

    def test_excludes_unpublished(self, client, db, author):
        Recipe.objects.create(
            title="Скрытый",
            ingredients=[{"name": "и"}],
            steps=[{"text": "ш"}],
            country="Япония",
            is_published=False,
            author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert "Япония" not in resp.data

    def test_excludes_empty_country(self, client, db, author):
        Recipe.objects.create(
            title="Без страны",
            ingredients=[{"name": "и"}],
            steps=[{"text": "ш"}],
            country="",
            is_published=True,
            author=author,
        )
        Recipe.objects.create(
            title="Только пробелы",
            ingredients=[{"name": "и"}],
            steps=[{"text": "ш"}],
            country="   ",
            is_published=True,
            author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert resp.data == []  # обе записи отфильтрованы

    def test_strips_whitespace(self, client, db, author):
        Recipe.objects.create(
            title="С пробелами",
            ingredients=[{"name": "и"}],
            steps=[{"text": "ш"}],
            country="  Франция  ",
            is_published=True,
            author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert "Франция" in resp.data


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ RecipeAuthorApplyView                                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestRecipeAuthorApply:
    def test_apply_success(self, client, plain_user):
        client.force_authenticate(plain_user)
        resp = client.post(
            reverse("recipe-author-apply"),
            {"motivation_text": "Хочу делиться рецептами"},
            format="json",
        )
        assert resp.status_code == 201
        assert RecipeAuthor.objects.filter(user=plain_user).exists()

    def test_apply_duplicate_raises_400(self, client, plain_user):
        RecipeAuthor.objects.create(user=plain_user, motivation_text="первая заявка")
        client.force_authenticate(plain_user)
        resp = client.post(
            reverse("recipe-author-apply"),
            {"motivation_text": "вторая попытка"},
            format="json",
        )
        assert resp.status_code == 400

    def test_apply_unauthenticated(self, client):
        resp = client.post(reverse("recipe-author-apply"), {}, format="json")
        assert resp.status_code == 401
