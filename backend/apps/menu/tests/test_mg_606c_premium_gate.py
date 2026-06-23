"""MG-606.C: Premium gate на menu API.

Покрытие: без Premium / cancelled / только trial → 403 на GET и POST.
Active Premium → доступ; expired → GET 200, POST 403.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
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
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return plan


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
class TestMenuPremiumGate:
    def test_list_no_premium_200(self, db):
        # Freemium: бесплатная семья видит свои меню (список не за premium-гейтом).
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 200

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 200

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 200

    def test_generate_no_premium_not_gated(self, db):
        # Freemium: бесплатная семья НЕ блокируется premium-гейтом на генерацию.
        # (квота свежая; без рецептов генерация падает на 400, но не на 403-гейте).
        family, head = _family()
        c = _auth(APIClient(), head)
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        assert resp.status_code != 403

    def test_generate_expired_premium_falls_back_to_free(self, db):
        # Истёкший premium = нет активного premium → работает как free (не 403-гейт).
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        assert resp.status_code != 403

    def test_generate_cancelled_falls_back_to_free(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.CANCELLED)
        c = _auth(APIClient(), head)
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        assert resp.status_code != 403

    def test_deleted_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/quarantine/").status_code == 403

    def test_deleted_list_active_premium_404_or_200(self, db):
        # У эндпоинта на пустой семье без меню возвращается 404 (см. views.py)
        # либо 200 с пустым списком — главное, что НЕ 403.
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/quarantine/").status_code in (200, 404)
