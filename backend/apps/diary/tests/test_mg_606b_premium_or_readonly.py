"""MG-606.B: тесты IsFamilyPremiumOrReadOnly на diary API.

Покрытие:
- active → GET 200, POST 201, PATCH 200, DELETE 204
- expired (active по статусу, дата прошла) → GET 200, POST 403, PATCH 403, DELETE 403
- cancelled (без active в истории) → GET 403, POST 403
- никогда не было → GET 403, POST 403
- trial → POST 201 (фича работает в триале), GET 403 (нет «реального опыта»)
- история active→expired → GET 200, POST 403
"""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ─── фабрики ───────────────────────────────────────────────────────────────


def _user(email):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family(email="head@e.com"):
    head = _user(email)
    family = Family.objects.create(owner=head, name="F")
    member = FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head, member


def _plan_premium():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return plan


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=_plan_premium(),
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _entry(member):
    return DiaryEntry.objects.create(
        member=member,
        date=date.today(),
        meal_type=DiaryEntry.MealType.BREAKFAST,
        custom_name="X",
        quantity=1,
        nutrition={"calories": {"value": 100}},
    )


def _auth(client, user):
    client.force_authenticate(user=user)
    return client


def _post_payload():
    return {
        "date": str(date.today()),
        "meal_type": "breakfast",
        "custom_name": "Toast",
        "quantity": 1,
        "nutrition": {"calories": {"value": 200}},
    }


# ─── 1. ACTIVE ─────────────────────────────────────────────────────────────


class TestActivePremium:
    def test_get_list_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_get_stats_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/stats/").status_code == 200

    def test_post_create_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201

    def test_patch_own_ok(self, db):
        family, head, head_m = _family()
        _sub(family, Subscription.Status.ACTIVE)
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        r = c.patch(f"/api/v1/diary/{e.id}/", {"custom_name": "Y"}, format="json")
        assert r.status_code == 200

    def test_delete_own_ok(self, db):
        family, head, head_m = _family()
        _sub(family, Subscription.Status.ACTIVE)
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        assert c.delete(f"/api/v1/diary/{e.id}/").status_code == 204


# ─── 2. EXPIRED (active-по-статусу, истёкший по дате) ──────────────────────


class TestExpiredPremium:
    """Самая важная группа: read остаётся, write закрыт."""

    def test_get_list_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_get_stats_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/stats/").status_code == 200

    def test_get_water_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/water/").status_code == 200

    def test_get_detail_ok(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get(f"/api/v1/diary/{e.id}/").status_code == 200

    def test_post_create_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403

    def test_patch_forbidden(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.patch(f"/api/v1/diary/{e.id}/", {"custom_name": "Y"}, format="json").status_code == 403

    def test_delete_forbidden(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.delete(f"/api/v1/diary/{e.id}/").status_code == 403

    def test_water_post_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/water/", {"date": str(date.today()), "ml": 500}, format="json")
        assert r.status_code == 403


# ─── 3. CANCELLED only / no sub ─────────────────────────────────────────────


class TestNeverHadPremium:
    def test_no_sub_get_forbidden(self, db):
        family, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_no_sub_post_forbidden(self, db):
        family, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403

    def test_cancelled_only_get_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.CANCELLED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_cancelled_only_post_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.CANCELLED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403


# ─── 4. TRIAL только ────────────────────────────────────────────────────────


class TestTrialOnly:
    """trial: write можно (фича включена пока триал жив), но read-после-истечения нет — это не «реальный опыт»."""

    def test_get_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.TRIAL)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_post_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.TRIAL)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201


# ─── 5. История: active → истёк по дате ────────────────────────────────────


class TestHistoryActiveThenExpired:
    """Реальная история: был active, истёк, новой подписки нет. read должен сохраниться."""

    def test_get_ok_after_active_expired(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-30)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_post_forbidden_after_active_expired(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-30)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403
