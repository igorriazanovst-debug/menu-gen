"""MG_FAMINVITE: в чужую семью попадают только по согласию.

До этой задачи ручка называлась «пригласить», но приглашения не было: сервер
находил аккаунт по почте или телефону и сразу создавал членство. Человек
оказывался за чужим столом, не узнав об этом, — с общим холодильником и списком
покупок, и с главой семьи, который получал право видеть и править его нормы
КБЖУ. Именно с этого начался разбор (chat-84): дочь пригласили, а у неё на
телефоне не появилось ничего.

Проверяется главное: до согласия не меняется ничего, после согласия человек
садится за новый стол, отказ ничего не ломает, а чужое приглашение неотличимо
от несуществующего.

Имена выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не семьи.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyInvite, FamilyMember
from apps.family.selection import current_family
from apps.users.models import User


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


def _family_with_head(user, name):
    family = Family.objects.create(owner=user, name=name)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return family


@pytest.fixture
def client():
    return APIClient()


def _with_seats(family, seats=5):
    """Бесплатный тариф — одно место, поэтому звать некого без плана побольше."""
    import datetime

    from django.utils import timezone

    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="test_seats",
        defaults={"name": "Проверочный", "price": 0, "max_family_members": seats},
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=365),
    )
    return family


@pytest.fixture
def head_and_guest(db):
    head = _user("glava@example.test", "Глава")
    family = _with_seats(_family_with_head(head, "Семья Зовущая"))
    guest = _user("gost@example.test", "Гость")
    own = _family_with_head(guest, "Семья Гостя")
    return head, family, guest, own


# ── приглашение не зачисляет ────────────────────────────────────────────────


@pytest.mark.django_db
def test_invite_creates_a_request_not_a_membership(client, head_and_guest):
    """Раньше эта же ручка молча сажала человека за чужой стол."""
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)

    resp = client.post(reverse("family-invite"), {"email": guest.email}, format="json")
    assert resp.status_code == 201
    assert resp.data["status"] == FamilyInvite.Status.PENDING
    assert resp.data["family_name"] == "Семья Зовущая"

    assert not FamilyMember.objects.filter(family=family, user=guest).exists()
    guest.refresh_from_db()
    assert current_family(guest) == own


@pytest.mark.django_db
def test_invited_person_is_told(client, head_and_guest):
    """Уведомление в приложении — единственный канал, который есть всегда."""
    from apps.notifications.models import Notification

    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    client.post(reverse("family-invite"), {"email": guest.email}, format="json")

    note = Notification.objects.filter(user=guest).first()
    assert note is not None
    assert "Семья Зовущая" in note.message


@pytest.mark.django_db
def test_guest_sees_the_invite(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    client.post(reverse("family-invite"), {"email": guest.email}, format="json")

    client.force_authenticate(guest)
    resp = client.get(reverse("family-invites"))
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["family_name"] == "Семья Зовущая"
    assert resp.data[0]["invited_by_name"] == "Глава"
    assert resp.data[0]["members_count"] == 1


@pytest.mark.django_db
def test_head_sees_who_has_not_answered_yet(client, head_and_guest):
    """Иначе приглашение выглядит как «нажал, и ничего не произошло»."""
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    client.post(reverse("family-invite"), {"email": guest.email}, format="json")

    resp = client.get(reverse("family-detail"))
    assert resp.status_code == 200
    assert [row["email"] for row in resp.data["pending_invites"]] == [guest.email]
    assert len(resp.data["members"]) == 1


# ── согласие ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_accepting_joins_and_switches_to_that_family(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    client.force_authenticate(guest)
    resp = client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": True}, format="json")
    assert resp.status_code == 200
    assert resp.data["status"] == FamilyInvite.Status.ACCEPTED

    assert FamilyMember.objects.filter(family=family, user=guest).exists()
    guest.refresh_from_db()
    # Человек только что сказал «да» — показывать ему прежнюю семью было бы странно.
    assert current_family(guest) == family

    detail = client.get(reverse("family-detail"))
    assert detail.data["name"] == "Семья Зовущая"


@pytest.mark.django_db
def test_after_accepting_own_family_is_still_available(client, head_and_guest):
    """Своя семья никуда не девается — в неё можно вернуться."""
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    client.force_authenticate(guest)
    client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": True}, format="json")

    choices = client.get(reverse("family-choices")).data
    by_id = {row["id"]: row for row in choices}
    assert set(by_id) == {own.id, family.id}
    assert by_id[family.id]["is_active"] is True
    assert by_id[own.id]["is_own"] is True

    client.post(reverse("family-switch"), {"family_id": own.id}, format="json")
    guest.refresh_from_db()
    assert current_family(guest) == own


# ── отказ и отзыв ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rejecting_changes_nothing(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    client.force_authenticate(guest)
    resp = client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": False}, format="json")
    assert resp.status_code == 200
    assert resp.data["status"] == FamilyInvite.Status.REJECTED

    assert not FamilyMember.objects.filter(family=family, user=guest).exists()
    guest.refresh_from_db()
    assert current_family(guest) == own
    assert client.get(reverse("family-invites")).data == []


@pytest.mark.django_db
def test_head_can_invite_again_after_a_refusal(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]
    client.force_authenticate(guest)
    client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": False}, format="json")

    client.force_authenticate(head)
    resp = client.post(reverse("family-invite"), {"email": guest.email}, format="json")
    assert resp.status_code == 201
    # Строка та же самая, второй не завелось: история отказов никому не нужна.
    assert resp.data["id"] == invite_id
    assert FamilyInvite.objects.filter(family=family, invited_user=guest).count() == 1

    client.force_authenticate(guest)
    assert len(client.get(reverse("family-invites")).data) == 1


@pytest.mark.django_db
def test_head_can_cancel_a_pending_invite(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    resp = client.delete(reverse("family-invite-cancel", args=[invite_id]))
    assert resp.status_code == 204

    client.force_authenticate(guest)
    assert client.get(reverse("family-invites")).data == []
    resp = client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": True}, format="json")
    assert resp.status_code == 404


# ── границы ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_someone_elses_invite_is_indistinguishable_from_a_missing_one(client, head_and_guest):
    head, family, guest, own = head_and_guest
    stranger = _user("chuzhoy@example.test", "Чужой")
    _family_with_head(stranger, "Семья Чужого")

    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    client.force_authenticate(stranger)
    resp = client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": True}, format="json")
    assert resp.status_code == 404
    assert not FamilyMember.objects.filter(family=family, user=stranger).exists()


@pytest.mark.django_db
def test_answering_twice_does_not_work(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    invite_id = client.post(reverse("family-invite"), {"email": guest.email}, format="json").data["id"]

    client.force_authenticate(guest)
    client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": True}, format="json")
    resp = client.post(reverse("family-invite-respond", args=[invite_id]), {"accept": False}, format="json")
    assert resp.status_code == 404
    assert FamilyMember.objects.filter(family=family, user=guest).exists()


@pytest.mark.django_db
def test_member_cannot_invite(client, head_and_guest):
    head, family, guest, own = head_and_guest
    member_user = _user("uchastnik@example.test", "Участник")
    FamilyMember.objects.create(family=family, user=member_user, role=FamilyMember.Role.MEMBER)
    member_user.active_family = family
    member_user.save(update_fields=["active_family"])

    client.force_authenticate(member_user)
    resp = client.post(reverse("family-invite"), {"email": guest.email}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_cannot_invite_yourself(client, head_and_guest):
    head, family, guest, own = head_and_guest
    client.force_authenticate(head)
    resp = client.post(reverse("family-invite"), {"email": head.email}, format="json")
    assert resp.status_code == 400
