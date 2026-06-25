"""MG-605.C — Premium gate + ?member_id= + PATCH владельцем.

Покрывает:
- Freemium: дневник открыт free-юзерам (read + write)
- ?member_id= для HEAD/MEMBER (403 / 404 / 200)
- PATCH /diary/{id}/ владельцем
- PATCH чужой записи (HEAD/MEMBER) → 404
- Запрет на изменение поля `member` через PATCH
- DELETE сохраняет существующее поведение
- DiaryStats с ?member_id=
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────


def _make_user(email):
    return User.objects.create_user(email=email, password="pwd12345!")


def _make_family_with_premium(owner_email="head@example.com", with_premium=True):
    head = _make_user(owner_email)
    family = Family.objects.create(owner=head, name="F")
    head_member = FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    if with_premium:
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0"), "period": SubscriptionPlan.Period.MONTH},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=30),
        )
    return family, head, head_member


def _add_member(family, email="m@example.com", role=FamilyMember.Role.MEMBER):
    user = _make_user(email)
    member = FamilyMember.objects.create(family=family, user=user, role=role)
    return user, member


def _make_entry(member, day=None, **kwargs):
    return DiaryEntry.objects.create(
        member=member,
        date=day or date.today(),
        meal_type=DiaryEntry.MealType.BREAKFAST,
        custom_name=kwargs.get("custom_name", "Toast"),
        quantity=kwargs.get("quantity", 1),
        nutrition=kwargs.get("nutrition", {"calories": {"value": 200}}),
    )


def _auth(client, user):
    client.force_authenticate(user=user)
    return client


def _list(resp):
    """MG-605.C: учёт DRF pagination — достаём results если есть."""
    data = resp.json()
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


# ─── 1) Premium gate ────────────────────────────────────────────────────────


class TestFreemiumAccess:
    """Freemium: дневник открыт free-юзерам (read + write). Premium тоже работает."""

    def test_free_user_list_ok(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 200

    def test_free_user_stats_ok(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/stats/").status_code == 200

    def test_free_user_water_ok(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/water/").status_code == 200

    def test_free_user_create_ok(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        resp = client.post(
            "/api/v1/diary/",
            {
                "date": str(date.today()),
                "meal_type": "breakfast",
                "custom_name": "X",
                "quantity": 1,
                "nutrition": {"calories": {"value": 100}},
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_active_premium_200(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 200


# ─── 2) ?member_id= — HEAD / MEMBER ─────────────────────────────────────────


class TestMemberIdFilter:
    def test_head_can_see_member_diary(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/?member_id={m_member.id}")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in _list(resp)]
        assert "MemberMeal" in names

    def test_member_cannot_see_other_member_diary(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        # просим дневник head с аккаунта member
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/?member_id={head_m.id}")
        assert resp.status_code == 403

    def test_member_can_see_own_via_member_id(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, custom_name="OwnMeal")
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/?member_id={m_member.id}")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in _list(resp)]
        assert "OwnMeal" in names

    def test_member_id_from_other_family_404(self, db):
        family, head, head_m = _make_family_with_premium("head1@example.com")
        family2, head2, head2_m = _make_family_with_premium("head2@example.com")
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/?member_id={head2_m.id}")
        assert resp.status_code == 404

    def test_member_id_unknown_404(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/?member_id=999999")
        assert resp.status_code == 404

    def test_member_id_invalid_404(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/?member_id=abc")
        assert resp.status_code == 404

    def test_without_member_id_returns_own(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(head_m, custom_name="HeadMeal")
        _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), m_user)
        resp = client.get("/api/v1/diary/")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in _list(resp)]
        assert "MemberMeal" in names and "HeadMeal" not in names


# ─── 3) PATCH /diary/{id}/ ──────────────────────────────────────────────────


class TestPatchOwner:
    def test_owner_can_patch_own(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A", quantity=1)
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True, "quantity": "2.5"}, format="json")
        assert resp.status_code == 200
        e.refresh_from_db()
        assert e.is_eaten is True
        assert e.quantity == Decimal("2.5")

    def test_member_cannot_patch_head_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(head_m, custom_name="HeadMeal")
        client = _auth(APIClient(), m_user)
        # MEMBER не видит чужую запись через get_queryset → 404
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True}, format="json")
        assert resp.status_code == 404

    def test_head_cannot_patch_member_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), head)
        # HEAD ВИДИТ (queryset включает всю семью), но не владелец → 403 (IsDiaryEntryOwner)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True}, format="json")
        assert resp.status_code == 403

    def test_patch_cannot_change_member(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"member": m_member.id, "is_eaten": True}, format="json")
        assert resp.status_code == 200
        e.refresh_from_db()
        assert e.member_id == head_m.id  # member не поменялся

    def test_patch_partial_recipe_or_custom_name_ok(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        # пустой PATCH — валидный (recipe или custom_name из instance)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"quantity": "3.0"}, format="json")
        assert resp.status_code == 200

    def test_patch_clears_both_fields_fails(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"custom_name": ""}, format="json")
        # recipe=None в instance, custom_name становится '' → ошибка
        assert resp.status_code == 400


# ─── 4) DELETE ──────────────────────────────────────────────────────────────


class TestDelete:
    def test_owner_can_delete_own(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m)
        client = _auth(APIClient(), head)
        resp = client.delete(f"/api/v1/diary/{e.id}/")
        assert resp.status_code == 204
        assert not DiaryEntry.objects.filter(pk=e.id).exists()

    def test_head_cannot_delete_member_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(m_member)
        client = _auth(APIClient(), head)
        # HEAD видит, но не владелец → 403
        resp = client.delete(f"/api/v1/diary/{e.id}/")
        assert resp.status_code == 403
        assert DiaryEntry.objects.filter(pk=e.id).exists()


# ─── 5) Stats с ?member_id= ─────────────────────────────────────────────────


class TestStatsMemberId:
    def test_head_stats_for_member(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, nutrition={"calories": {"value": 500}})
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/stats/?member_id={m_member.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # MG-605.D: вложенная структура; запись без planned_menu_item → actual
        assert data[0]["actual"]["calories"] == 500.0

    def test_member_stats_other_403(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/stats/?member_id={head_m.id}")
        assert resp.status_code == 403
