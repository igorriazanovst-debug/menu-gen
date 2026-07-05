"""MG_ALLERGEN: freemium collapsed product catalog for allergen picking.

Проверяем, что /fridge/products/catalog/:
  - доступен обычному (free, без premium) пользователю — это общий справочник;
  - схлопывает варианты продукта в один базовый аллерген;
  - поддерживает ?q= фильтр.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.fridge.models import Product, ProductCategory

User = get_user_model()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def free_user(db):
    # Никакой семьи/подписки — самый обычный free-пользователь.
    return User.objects.create_user(email="free@a.a", password="x", name="Free")


@pytest.mark.django_db
class TestAllergenCatalog:
    def test_requires_auth(self, client):
        r = client.get(reverse("product-catalog"))
        assert r.status_code in (401, 403)

    def test_free_user_can_browse(self, client, free_user):
        client.force_authenticate(free_user)
        r = client.get(reverse("product-catalog"))
        assert r.status_code == 200, r.content
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) > 0  # сиды продуктов присутствуют
        assert "name" in rows[0]
        assert "key" in rows[0]
        assert "category_name" in rows[0]
        assert "examples" in rows[0]

    def test_variants_collapse_to_one_base(self, client, free_user):
        Product.objects.create(name="Сыр гауда")
        Product.objects.create(name="Сыр тёртый")
        Product.objects.create(name="Сыр российский")
        client.force_authenticate(free_user)
        r = client.get(reverse("product-catalog"), {"q": "сыр"})
        assert r.status_code == 200, r.content
        rows = r.json()
        cheese = [row for row in rows if row["key"] == "сыр"]
        assert len(cheese) == 1, rows
        entry = cheese[0]
        assert entry["name"] == "Сыр"
        # примеры включают исходные варианты
        assert any("гауда" in e.lower() for e in entry["examples"])
        assert any("тёртый" in e.lower() or "тертый" in e.lower() for e in entry["examples"])

    def test_query_filters(self, client, free_user):
        Product.objects.create(name="Арахис жареный")
        Product.objects.create(name="Морковь свежая")
        client.force_authenticate(free_user)
        r = client.get(reverse("product-catalog"), {"q": "арахис"})
        assert r.status_code == 200, r.content
        keys = [row["key"] for row in r.json()]
        assert "арахис" in keys
        assert "морковь" not in keys

    def test_non_food_and_ready_excluded(self, client, free_user):
        # непищевые категории и готовые блюда не должны попадать в аллергены
        household = ProductCategory.objects.create(slug="household", name_ru="Бытовая химия")
        ready = ProductCategory.objects.create(slug="ready", name_ru="Готовые блюда")
        dairy, _ = ProductCategory.objects.get_or_create(slug="dairy", defaults={"name_ru": "Молочные продукты"})
        Product.objects.create(name="Стиральный порошок", category_fk=household)
        Product.objects.create(name="Плов готовый", category_fk=ready)
        Product.objects.create(name="Кефир тестовый", category_fk=dairy)

        client.force_authenticate(free_user)
        r = client.get(reverse("product-catalog"))
        assert r.status_code == 200, r.content
        keys = [row["key"] for row in r.json()]
        assert "стиральный" not in keys
        assert "плов" not in keys
        assert "кефир" in keys
