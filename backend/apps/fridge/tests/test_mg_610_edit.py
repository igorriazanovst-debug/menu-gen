"""MG-610: bulk-delete expired + history edit endpoints."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="mg610@dev.local", password="x", name="MG610")
    family = Family.objects.create(name="F610", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": "0.00"},
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    client = APIClient()
    client.force_authenticate(user)
    return client, family, user


def _mk(family, name, days_offset, deleted=False):
    today = timezone.now().date()
    return FridgeItem.objects.create(
        family=family,
        name=name,
        quantity=1,
        unit="шт",
        expiry_date=today + datetime.timedelta(days=days_offset),
        is_deleted=deleted,
    )


# ── MG_610_V_expired_bulk ────────────────────────────────────────────────────
@pytest.mark.django_db
class TestExpiredBulkDelete:
    def test_delete_selected_soft(self, setup):
        client, family, _ = setup
        e1 = _mk(family, "Молоко", -3)
        e2 = _mk(family, "Кефир", -1)
        ok = _mk(family, "Сыр", +5)
        r = client.post(
            "/api/v1/fridge/expired/delete/",
            {"ids": [e1.id], "drop_history": False},
            format="json",
        )
        assert r.status_code == 200, r.content
        assert r.data["deleted"] == 1
        e1.refresh_from_db()
        assert e1.is_deleted is True
        assert FridgeItem.objects.filter(id=e2.id, is_deleted=False).exists()
        assert FridgeItem.objects.filter(id=ok.id, is_deleted=False).exists()

    def test_delete_all_soft(self, setup):
        client, family, _ = setup
        _mk(family, "A", -2)
        _mk(family, "B", -5)
        _mk(family, "C", +10)
        r = client.post(
            "/api/v1/fridge/expired/delete/",
            {"all": True},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["deleted"] == 2
        assert FridgeItem.objects.filter(family=family, is_deleted=False).count() == 1

    def test_delete_drop_history_hard(self, setup):
        client, family, _ = setup
        e1 = _mk(family, "X", -1)
        r = client.post(
            "/api/v1/fridge/expired/delete/",
            {"ids": [e1.id], "drop_history": True},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["deleted"] == 1
        assert not FridgeItem.objects.filter(id=e1.id).exists()

    def test_non_expired_not_touched(self, setup):
        client, family, _ = setup
        ok = _mk(family, "Fresh", +3)
        r = client.post(
            "/api/v1/fridge/expired/delete/",
            {"ids": [ok.id]},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["deleted"] == 0
        assert FridgeItem.objects.filter(id=ok.id, is_deleted=False).exists()

    def test_empty_ids_400(self, setup):
        client, _, _ = setup
        r = client.post("/api/v1/fridge/expired/delete/", {}, format="json")
        assert r.status_code == 400


# ── MG_610_V_history_entry ───────────────────────────────────────────────────
@pytest.mark.django_db
class TestHistoryEntryDelete:
    def test_remove_from_history_only_keeps_active(self, setup):
        client, family, _ = setup
        active = _mk(family, "Хлеб", +5, deleted=False)
        old = _mk(family, "хлеб", +1, deleted=True)  # case-insensitive same name
        r = client.delete("/api/v1/fridge/products/history/Хлеб/")
        assert r.status_code == 200, r.content
        assert r.data["deleted"] == 1
        assert FridgeItem.objects.filter(id=active.id).exists()
        assert not FridgeItem.objects.filter(id=old.id).exists()

    def test_drop_fridge_removes_all(self, setup):
        client, family, _ = setup
        a = _mk(family, "Масло", +5, deleted=False)
        b = _mk(family, "масло", +1, deleted=True)
        r = client.delete("/api/v1/fridge/products/history/Масло/?drop_fridge=1")
        assert r.status_code == 200
        assert r.data["deleted"] == 2
        assert not FridgeItem.objects.filter(id__in=[a.id, b.id]).exists()

    def test_unknown_name_zero(self, setup):
        client, _, _ = setup
        r = client.delete("/api/v1/fridge/products/history/Несуществует/")
        assert r.status_code == 200
        assert r.data["deleted"] == 0
