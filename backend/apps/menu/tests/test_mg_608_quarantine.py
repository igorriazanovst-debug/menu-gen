"""MG-608: тесты карантина — purge, purge-all, expired filter, celery beat task."""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import DeletedMenu
from apps.menu.tasks import purge_expired_menus
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


def _mk_user(email="u@example.com", name="U", user_type="user"):
    return User.objects.create_user(email=email, name=name, password="x12345", user_type=user_type)


def _attach_premium(fam):
    """Тот же шаблон, что в test_mg_602_views.py — но через рефлексию полей."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan_fields = {f.name for f in SubscriptionPlan._meta.get_fields() if not f.is_relation or f.many_to_one}
    defaults = {"name": "Premium"}
    if "price" in plan_fields:
        defaults["price"] = 100
    if "price_monthly" in plan_fields:
        defaults["price_monthly"] = 100
    if "duration_days" in plan_fields:
        defaults["duration_days"] = 30
    if "billing_period_days" in plan_fields:
        defaults["billing_period_days"] = 30
    plan, _ = SubscriptionPlan.objects.get_or_create(code="premium", defaults=defaults)

    sub_fields = {f.name for f in Subscription._meta.get_fields() if not f.is_relation or f.many_to_one}
    sub_kwargs = {"family": fam, "plan": plan, "status": Subscription.Status.ACTIVE}
    if "starts_at" in sub_fields:
        sub_kwargs["starts_at"] = timezone.now()
    if "expires_at" in sub_fields:
        sub_kwargs["expires_at"] = timezone.now() + datetime.timedelta(days=30)
    if "started_at" in sub_fields:
        sub_kwargs["started_at"] = timezone.now()
    Subscription.objects.create(**sub_kwargs)


def _mk_family(user, role=None):
    fam = Family.objects.create(owner=user, name=f"F {user.name}")
    _attach_premium(fam)
    FamilyMember.objects.create(family=fam, user=user, role=role or FamilyMember.Role.HEAD)
    return fam


def _mk_deleted(fam, user, purge_after, menu_id=999):
    return DeletedMenu.objects.create(
        menu_id=menu_id,
        family=fam,
        deleted_by=user,
        data={
            "id": menu_id,
            "start_date": str(datetime.date.today()),
            "end_date": str(datetime.date.today()),
            "period_days": 1,
            "status": "active",
            "filters_used": {},
            "items": [],
        },
        purge_after=purge_after,
    )


# ─── DeletedMenuListView фильтрует expired ─────────────────────────────
@pytest.mark.django_db
class TestMg608QuarantineListFilters:
    def test_expired_records_hidden(self, client, db):
        user = _mk_user(email="mg608_q1@x.com")
        fam = _mk_family(user)
        client.force_authenticate(user)
        _mk_deleted(fam, user, timezone.now() + datetime.timedelta(hours=10), menu_id=101)
        _mk_deleted(fam, user, timezone.now() + datetime.timedelta(hours=20), menu_id=102)
        _mk_deleted(fam, user, timezone.now() - datetime.timedelta(hours=1), menu_id=103)
        _mk_deleted(fam, user, timezone.now() - datetime.timedelta(days=2), menu_id=104)
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 200
        ids = sorted(r["menu_id"] for r in resp.data)
        assert ids == [101, 102]


# ─── MenuRestoreView: expired → 403 ────────────────────────────────────
@pytest.mark.django_db
class TestMg608RestoreExpired:
    def test_restore_expired_returns_403(self, client, db):
        user = _mk_user(email="mg608_re@x.com")
        fam = _mk_family(user)
        client.force_authenticate(user)
        d = _mk_deleted(fam, user, timezone.now() - datetime.timedelta(hours=1))
        resp = client.post(reverse("menu-restore", args=[d.id]))
        assert resp.status_code == 403
        assert "истёк" in resp.data["detail"].lower()
        assert DeletedMenu.objects.filter(id=d.id).exists()


# ─── MenuPurgeView ─────────────────────────────────────────────────────
@pytest.mark.django_db
class TestMg608PurgeOne:
    def test_purge_success_creator(self, client, db):
        user = _mk_user(email="mg608_p1@x.com")
        fam = _mk_family(user)
        client.force_authenticate(user)
        d = _mk_deleted(fam, user, timezone.now() + datetime.timedelta(hours=10))
        resp = client.delete(reverse("menu-purge", args=[d.id]))
        assert resp.status_code == 204
        assert not DeletedMenu.objects.filter(id=d.id).exists()

    def test_purge_no_family_403(self, client, db):
        u = _mk_user(email="mg608_p2@x.com")
        client.force_authenticate(u)
        resp = client.delete(reverse("menu-purge", args=[1]))
        assert resp.status_code == 403  # premium-gate без семьи

    def test_purge_not_found(self, client, db):
        user = _mk_user(email="mg608_p3@x.com")
        _mk_family(user)
        client.force_authenticate(user)
        resp = client.delete(reverse("menu-purge", args=[99999]))
        assert resp.status_code == 404

    def test_purge_no_permission(self, client, db):
        head = _mk_user(email="mg608_p4h@x.com", name="HD")
        other = _mk_user(email="mg608_p4o@x.com", name="OT")
        fam = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=other, role=FamilyMember.Role.MEMBER)
        d = _mk_deleted(fam, head, timezone.now() + datetime.timedelta(hours=10))
        client.force_authenticate(other)
        resp = client.delete(reverse("menu-purge", args=[d.id]))
        assert resp.status_code == 403


# ─── MenuPurgeAllView ──────────────────────────────────────────────────
@pytest.mark.django_db
class TestMg608PurgeAll:
    def test_purge_all_success_head(self, client, db):
        head = _mk_user(email="mg608_pa1@x.com", name="PA")
        fam = _mk_family(head)
        client.force_authenticate(head)
        _mk_deleted(fam, head, timezone.now() + datetime.timedelta(hours=10), menu_id=201)
        _mk_deleted(fam, head, timezone.now() + datetime.timedelta(hours=20), menu_id=202)
        _mk_deleted(fam, head, timezone.now() - datetime.timedelta(hours=1), menu_id=203)
        resp = client.delete(reverse("menu-purge-all"))
        assert resp.status_code == 200
        assert resp.data["deleted"] == 3
        assert DeletedMenu.objects.filter(family=fam).count() == 0

    def test_purge_all_member_returns_403(self, client, db):
        head = _mk_user(email="mg608_pa2h@x.com", name="H")
        member = _mk_user(email="mg608_pa2m@x.com", name="M")
        fam = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=member, role=FamilyMember.Role.MEMBER)
        _mk_deleted(fam, head, timezone.now() + datetime.timedelta(hours=10))
        client.force_authenticate(member)
        resp = client.delete(reverse("menu-purge-all"))
        assert resp.status_code == 403

    def test_purge_all_admin_can(self, client, db):
        admin = _mk_user(email="mg608_pa3a@x.com", name="A", user_type="admin")
        owner = _mk_user(email="mg608_pa3o@x.com", name="O")
        fam = _mk_family(owner)
        FamilyMember.objects.create(family=fam, user=admin, role=FamilyMember.Role.MEMBER)
        _mk_deleted(fam, owner, timezone.now() + datetime.timedelta(hours=10))
        client.force_authenticate(admin)
        resp = client.delete(reverse("menu-purge-all"))
        assert resp.status_code == 200


# ─── celery task: purge_expired_menus ─────────────────────────────────
@pytest.mark.django_db
class TestMg608PurgeExpiredTask:
    def test_task_removes_only_expired(self, db):
        user = _mk_user(email="mg608_t1@x.com")
        fam = _mk_family(user)
        live = _mk_deleted(fam, user, timezone.now() + datetime.timedelta(hours=5), menu_id=301)
        old = _mk_deleted(fam, user, timezone.now() - datetime.timedelta(hours=5), menu_id=302)
        cnt = purge_expired_menus()
        assert cnt == 1
        assert DeletedMenu.objects.filter(id=live.id).exists()
        assert not DeletedMenu.objects.filter(id=old.id).exists()
