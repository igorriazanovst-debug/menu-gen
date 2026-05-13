"""MG-606.C: Premium gate on notifications API.

Endpoints:
- GET  /api/v1/notifications/               — list
- POST /api/v1/notifications/{id}/read/     — mark-read

Coverage:
- no premium → 403 on both
- active premium → 200 list, 200 mark-read
- expired (active+date past) → 200 list, 403 mark-read
- cancelled-only → 403 on both
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.notifications.models import Notification
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
        family=family, plan=_plan(), status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _notif(user):
    return Notification.objects.create(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title="t",
        message="m",
    )


def _auth(c, u):
    c.force_authenticate(u)
    return c


@pytest.mark.django_db
class TestNotificationsPremiumGate:
    def test_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 403

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 200

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 200

    def test_list_cancelled_only_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.CANCELLED)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 403

    def test_mark_read_no_premium_403(self, db):
        family, head = _family()
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 403

    def test_mark_read_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 200

    def test_mark_read_expired_premium_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 403
