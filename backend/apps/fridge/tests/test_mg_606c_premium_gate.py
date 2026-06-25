"""MG-606.C: Premium gate на fridge API.

Покрытие: без Premium → 403, active → 200, expired (active+истёкший по дате) → GET 200, POST 403.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _user(email="m@e.com"):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family():
    head = _user()
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _plan():
    p, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return p


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=_plan(),
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _auth(c, u):
    c.force_authenticate(u)
    return c


@pytest.mark.django_db
class TestFridgePremiumGate:
    def test_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 403

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 200

    def test_create_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 403

    def test_create_active_premium_201(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 201

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 200

    def test_create_expired_premium_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 403

    def test_barcode_scan_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-scan"), {"barcode": "1234567890"}, format="json")
        assert resp.status_code == 403

    def test_product_search_open_to_free_200(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        # freemium: каталог продуктов (КБЖУ) открыт free-юзерам — используется
        # ручным добавлением продукта в дневник.
        assert c.get("/api/v1/fridge/products/search/").status_code == 200
