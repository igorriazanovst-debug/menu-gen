import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def head(db):
    u = User.objects.create_user(email="head@example.com", name="Глава", password="pass1234")
    family = Family.objects.create(owner=u, name="Тест семья")
    FamilyMember.objects.create(family=family, user=u, role=FamilyMember.Role.HEAD)
    return u


@pytest.fixture
def other(db):
    return User.objects.create_user(email="other@example.com", name="Другой", password="pass1234")


@pytest.mark.django_db
class TestFamilyDetail:
    def test_get_family(self, client, head):
        client.force_authenticate(head)
        resp = client.get(reverse("family-detail"))
        assert resp.status_code == 200
        assert resp.data["name"] == "Тест семья"
        assert len(resp.data["members"]) == 1

    def test_get_no_family(self, client, other):
        client.force_authenticate(other)
        resp = client.get(reverse("family-detail"))
        assert resp.status_code == 404

    def test_patch_name(self, client, head):
        client.force_authenticate(head)
        resp = client.patch(reverse("family-detail"), {"name": "Новое имя"}, format="json")
        assert resp.status_code == 200
        assert resp.data["name"] == "Новое имя"

    def test_patch_by_non_head_forbidden(self, client, head, other):
        family = Family.objects.get(owner=head)
        FamilyMember.objects.create(family=family, user=other, role=FamilyMember.Role.MEMBER)
        client.force_authenticate(other)
        resp = client.patch(reverse("family-detail"), {"name": "Взлом"}, format="json")
        assert resp.status_code == 403

    def test_unauthenticated(self, client):
        resp = client.get(reverse("family-detail"))
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFamilyInvite:
    def test_invite_success(self, client, head, other):
        client.force_authenticate(head)
        resp = client.post(reverse("family-invite"), {"email": other.email}, format="json")
        assert resp.status_code == 201
        family = Family.objects.get(owner=head)
        assert FamilyMember.objects.filter(family=family, user=other).exists()

    def test_invite_already_member(self, client, head, other):
        family = Family.objects.get(owner=head)
        FamilyMember.objects.create(family=family, user=other, role=FamilyMember.Role.MEMBER)
        client.force_authenticate(head)
        resp = client.post(reverse("family-invite"), {"email": other.email}, format="json")
        assert resp.status_code == 400

    def test_invite_user_not_found(self, client, head):
        client.force_authenticate(head)
        resp = client.post(reverse("family-invite"), {"email": "nobody@example.com"}, format="json")
        assert resp.status_code == 404

    def test_invite_limit_exceeded(self, client, head, other):
        plan = SubscriptionPlan.objects.create(
            code="free_test", name="Бесплатный", price=0, max_family_members=1
        )
        from apps.subscriptions.models import Subscription
        from django.utils import timezone
        import datetime
        family = Family.objects.get(owner=head)
        Subscription.objects.create(
            family=family, plan=plan, status=Subscription.Status.ACTIVE,
            started_at=timezone.now(), expires_at=timezone.now() + datetime.timedelta(days=365)
        )
        client.force_authenticate(head)
        resp = client.post(reverse("family-invite"), {"email": other.email}, format="json")
        assert resp.status_code == 403

    def test_invite_by_non_head_forbidden(self, client, head, other):
        family = Family.objects.get(owner=head)
        third = User.objects.create_user(email="third@example.com", name="Третий", password="pass1234")
        FamilyMember.objects.create(family=family, user=other, role=FamilyMember.Role.MEMBER)
        client.force_authenticate(other)
        resp = client.post(reverse("family-invite"), {"email": third.email}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestFamilyRemoveMember:
    def test_remove_member_by_head(self, client, head, other):
        family = Family.objects.get(owner=head)
        member = FamilyMember.objects.create(family=family, user=other, role=FamilyMember.Role.MEMBER)
        client.force_authenticate(head)
        resp = client.delete(reverse("family-remove-member", args=[member.id]))
        assert resp.status_code == 204

    def test_remove_head_forbidden(self, client, head):
        family = Family.objects.get(owner=head)
        head_member = FamilyMember.objects.get(family=family, user=head)
        client.force_authenticate(head)
        resp = client.delete(reverse("family-remove-member", args=[head_member.id]))
        assert resp.status_code == 400

    def test_self_remove(self, client, head, other):
        family = Family.objects.get(owner=head)
        member = FamilyMember.objects.create(family=family, user=other, role=FamilyMember.Role.MEMBER)
        client.force_authenticate(other)
        resp = client.delete(reverse("family-remove-member", args=[member.id]))
        assert resp.status_code == 204
