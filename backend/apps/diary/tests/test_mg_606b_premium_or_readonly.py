"""Freemium: дневник питания открыт free-юзерам (write + read).

Ранее diary был под IsFamilyPremiumOrReadOnly (read — только при наличии
premium в истории, write — только при активном premium). В рамках freemium
гейт снят: дневник доступен любому авторизованному пользователю, реальная
авторизация (владелец записи / HEAD) — на уровне IsDiaryEntryOwner и
_resolve_target_member, см. test_mg_605c_permissions.py.

Этот файл проверяет, что free-юзер (без какой-либо подписки) получает полный
доступ к своему дневнику, и что premium-юзер по-прежнему работает.
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


# ─── 1. FREE-юзер (без подписки) — полный доступ ────────────────────────────


class TestFreeUserFullAccess:
    def test_get_list_ok(self, db):
        _, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_get_stats_ok(self, db):
        _, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/stats/").status_code == 200

    def test_get_water_ok(self, db):
        _, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/water/").status_code == 200

    def test_get_detail_ok(self, db):
        _, head, head_m = _family()
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        assert c.get(f"/api/v1/diary/{e.id}/").status_code == 200

    def test_post_create_ok(self, db):
        _, head, _ = _family()
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201

    def test_patch_own_ok(self, db):
        _, head, head_m = _family()
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        r = c.patch(f"/api/v1/diary/{e.id}/", {"custom_name": "Y"}, format="json")
        assert r.status_code == 200

    def test_delete_own_ok(self, db):
        _, head, head_m = _family()
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        assert c.delete(f"/api/v1/diary/{e.id}/").status_code == 204

    def test_water_post_ok(self, db):
        _, head, _ = _family()
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/water/", {"date": str(date.today()), "water_ml": 500}, format="json")
        assert r.status_code in (200, 201)


# ─── 2. PREMIUM-юзер — по-прежнему работает (sanity) ────────────────────────


class TestPremiumStillWorks:
    def test_get_list_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_post_create_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201
