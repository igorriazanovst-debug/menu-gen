"""Tests for OpenFoodFacts fallback in BarcodeLookupView."""
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import Product
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _family_with_premium():
    user = User.objects.create_user(email="t@t.t", password="x", name="T")
    family = Family.objects.create(name="F", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": "0", "period": "month"},
    )
    from django.utils import timezone
    import datetime
    Subscription.objects.create(
        family=family, plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user


def _auth(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
def test_barcode_found_locally():
    user = _family_with_premium()
    Product.objects.create(name="Молоко", barcode="4601234500000")
    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "4601234500000"}, format="json")
    assert resp.status_code == 200
    assert resp.data["name"] == "Молоко"
    assert resp.data["source"] == "local"


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_fallback_off_creates_product(mock_get):
    user = _family_with_premium()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 1,
        "product": {
            "product_name_ru": "Хлеб бородинский",
            "categories": "Хлеб, выпечка",
            "image_front_url": "https://example.org/img.jpg",
            "nutriments": {
                "energy-kcal_100g": 250,
                "proteins_100g": 8,
                "fat_100g": 1.5,
                "carbohydrates_100g": 50,
                "fiber_100g": 6,
            },
        },
    }
    mock_get.return_value = mock_resp

    c = _auth(user)
    assert not Product.objects.filter(barcode="4607000000000").exists()
    resp = c.post(reverse("fridge-scan"), {"barcode": "4607000000000"}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.data["name"] == "Хлеб бородинский"
    assert resp.data["source"] == "openfoodfacts"
    assert resp.data["image_url"] == "https://example.org/img.jpg"
    cached = Product.objects.get(barcode="4607000000000")
    assert cached.name == "Хлеб бородинский"


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_off_returns_not_found(mock_get):
    user = _family_with_premium()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 0}
    mock_get.return_value = mock_resp

    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "0000000000000"}, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_off_timeout_returns_404(mock_get):
    import requests
    user = _family_with_premium()
    mock_get.side_effect = requests.Timeout("simulated")

    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "0000000000001"}, format="json")
    assert resp.status_code == 404
