"""MG_ALLERGEN: freemium browsable product catalog for allergen picking.

Проверяем, что /fridge/products/catalog/:
  - доступен обычному (free, без premium) пользователю — это общий справочник;
  - возвращает продукты; поддерживает ?q= фильтр по названию.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.fridge.models import Product

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
        # плоский (не пагинированный) список с ожидаемыми полями
        assert "name" in rows[0]
        assert "category_name" in rows[0]

    def test_query_filters(self, client, free_user):
        Product.objects.create(name="Тестовый арахис")
        Product.objects.create(name="Морковь тестовая")
        client.force_authenticate(free_user)
        r = client.get(reverse("product-catalog"), {"q": "арахис"})
        assert r.status_code == 200, r.content
        names = [row["name"] for row in r.json()]
        assert any("арахис" in n.lower() for n in names)
        assert all("морковь" not in n.lower() for n in names)
