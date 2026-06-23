"""MG-profile-premium: tests for UserMeSerializer.subscription_status.

Проверяет derived-поле subscription_status в ответе GET /users/me/:
- нет семьи → None
- active premium → {is_active=True, has_ever=True, plan='premium', status='active'}
- trial premium → {is_active=True, has_ever=False} (по B13)
- expired premium → {is_active=False, has_ever=True}
- cancelled только → {is_active=False, has_ever=False}
- basic (не premium) → {is_active=False, has_ever=False, plan='basic'}
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User
from apps.users.serializers import UserMeSerializer

# ─── фикстуры ───────────────────────────────────────────────────────────────


@pytest.fixture
def plan_premium(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("499")},
    )
    return plan


@pytest.fixture
def plan_basic(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="basic",
        defaults={"name": "Basic", "price": Decimal("0")},
    )
    return plan


def _user(email):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family(owner_email):
    head = _user(owner_email)
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _sub(family, plan, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=plan,
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _serialize(user):
    factory = APIRequestFactory()
    req = Request(factory.get("/"))
    req.user = user
    return UserMeSerializer(user, context={"request": req}).data


# ─── тесты ──────────────────────────────────────────────────────────────────


class TestSubscriptionStatusField:
    def test_no_family_returns_none(self, db):
        u = _user("lone@e.com")
        data = _serialize(u)
        assert data["subscription_status"] is None

    def test_family_no_subscription_returns_payload_with_false_flags(self, db):
        _, head = _family("h1@e.com")
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is False
        assert data["has_ever_premium"] is False
        assert data["plan_code"] is None
        assert data["status"] is None
        assert data["expires_at"] is None
        # Freemium: бесплатная семья получает квоту free-плана (4/мес, 0 использовано).
        assert data["menu_quota"]["limit"] == 4
        assert data["menu_quota"]["used"] == 0
        assert "reset_at" in data["menu_quota"]

    def test_active_premium(self, db, plan_premium):
        family, head = _family("h2@e.com")
        sub = _sub(family, plan_premium, Subscription.Status.ACTIVE)
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is True
        assert data["has_ever_premium"] is True
        assert data["plan_code"] == "premium"
        assert data["status"] == "active"
        assert data["expires_at"] == sub.expires_at.isoformat()

    def test_trial_is_active_but_not_ever(self, db, plan_premium):
        family, head = _family("h3@e.com")
        _sub(family, plan_premium, Subscription.Status.TRIAL)
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is True
        assert data["has_ever_premium"] is False
        assert data["status"] == "trial"

    def test_expired_premium(self, db, plan_premium):
        family, head = _family("h4@e.com")
        _sub(
            family,
            plan_premium,
            Subscription.Status.EXPIRED,
            expires_in_days=-5,
        )
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is False
        assert data["has_ever_premium"] is True
        assert data["status"] == "expired"

    def test_cancelled_only(self, db, plan_premium):
        family, head = _family("h5@e.com")
        _sub(family, plan_premium, Subscription.Status.CANCELLED)
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is False
        assert data["has_ever_premium"] is False
        assert data["status"] == "cancelled"

    def test_basic_plan_not_premium(self, db, plan_basic):
        family, head = _family("h6@e.com")
        _sub(family, plan_basic, Subscription.Status.ACTIVE)
        data = _serialize(head)["subscription_status"]
        assert data["is_active_premium"] is False
        assert data["has_ever_premium"] is False
        assert data["plan_code"] == "basic"
        assert data["status"] == "active"

    def test_latest_subscription_wins(self, db, plan_premium):
        """При нескольких подписках — отдаём последнюю по started_at."""
        family, head = _family("h7@e.com")
        # Старая expired
        _sub(
            family,
            plan_premium,
            Subscription.Status.EXPIRED,
            expires_in_days=-100,
        )
        # Свежая active
        latest = _sub(family, plan_premium, Subscription.Status.ACTIVE)
        # Сдвинем started_at старой ещё дальше в прошлое
        old = Subscription.objects.filter(family=family).exclude(id=latest.id).first()
        old.started_at = timezone.now() - timedelta(days=200)
        old.save()

        data = _serialize(head)["subscription_status"]
        assert data["status"] == "active"
        assert data["is_active_premium"] is True
        assert data["has_ever_premium"] is True
