"""MG_ACCDEL: удаление аккаунта — запрос, отмена, стирание.

Проверяется то, что ломается молча и дорого:

* замороженный аккаунт не работает по токену (иначе «удаление» было бы
  косметическим);
* вход возвращает аккаунт к жизни (иначе отменить нечем);
* семья с живыми участниками переживает уход главы, а данные не своих семей
  не трогаются;
* платежи переживают стирание — это бухгалтерия, а не пользовательские данные.

Имена и адреса выдуманные: в тестовой базе есть посевной каталог продуктов
(миграция fridge 0004), но не пользователи — здесь пересечься не с чем.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.payments.models import Payment
from apps.users.account_deletion import GRACE_DAYS, cancel_deletion, purge_user, request_deletion
from apps.users.models import User

PASSWORD = "ochen-sekretno-77"


def _user(email, name="Тестовый", **kwargs):
    user = User.objects.create_user(email=email, name=name, password=PASSWORD, **kwargs)
    # Гейт подтверждения e-mail не относится к делу и мешал бы каждому входу.
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def _family(owner, name="Семья Кринжелевых"):
    family = Family.objects.create(owner=owner, name=name)
    FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return family


def _auth(user):
    from apps.users.serializers import TokenPairSerializer

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + TokenPairSerializer.get_tokens(user)["access"])
    return client


# ─── запрос удаления ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_request_freezes_account_and_sets_deadline():
    user = _user("zamorozka@example.invalid")
    purge_at = request_deletion(user)
    user.refresh_from_db()

    assert user.is_active is False
    assert user.deletion_requested_at is not None
    assert purge_at - user.deletion_requested_at == timedelta(days=GRACE_DAYS)


@pytest.mark.django_db
def test_request_is_idempotent():
    user = _user("dvazhdy@example.invalid")
    first = request_deletion(user)
    second = request_deletion(user)
    assert first == second


@pytest.mark.django_db
def test_frozen_token_stops_working():
    """Заморозка должна быть настоящей, а не отметкой в базе."""
    user = _user("token@example.invalid")
    client = _auth(user)
    assert client.get(reverse("users-me")).status_code == 200

    request_deletion(user)
    assert client.get(reverse("users-me")).status_code == 401


@pytest.mark.django_db
def test_api_requires_correct_password():
    user = _user("parol@example.invalid")
    client = _auth(user)

    resp = client.post(reverse("users-me-delete"), {"password": "ne-tot-parol"}, format="json")
    assert resp.status_code == 400
    assert resp.data["code"] == "invalid_password"
    user.refresh_from_db()
    assert user.deletion_requested_at is None

    resp = client.post(reverse("users-me-delete"), {"password": PASSWORD}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
def test_preview_names_what_is_lost():
    """Экран подтверждения должен знать, уедет ли семья вместе с человеком."""
    alone = _user("odin@example.invalid")
    _family(alone, name="Семья Одиночкиных")
    data = _auth(alone).get(reverse("users-me-delete")).data
    assert data["family_data_will_be_deleted"] is True
    assert data["families_to_delete"] == ["Семья Одиночкиных"]

    head = _user("glava@example.invalid")
    family = _family(head)
    heir = _user("naslednik@example.invalid", name="Наследник")
    FamilyMember.objects.create(family=family, user=heir)
    data = _auth(head).get(reverse("users-me-delete")).data
    assert data["family_data_will_be_deleted"] is False
    assert data["new_owners"] == ["Наследник"]


# ─── отмена входом ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_login_cancels_deletion():
    user = _user("peredumal@example.invalid")
    request_deletion(user)

    resp = APIClient().post(
        reverse("auth-login"),
        {"email": "peredumal@example.invalid", "password": PASSWORD},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["deletion_cancelled"] is True

    user.refresh_from_db()
    assert user.is_active is True
    assert user.deletion_requested_at is None


@pytest.mark.django_db
def test_login_with_wrong_password_does_not_revive():
    user = _user("chuzhoy@example.invalid")
    request_deletion(user)

    resp = APIClient().post(
        reverse("auth-login"),
        {"email": "chuzhoy@example.invalid", "password": "podbor"},
        format="json",
    )
    assert resp.status_code == 400
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_disabled_account_still_cannot_log_in():
    """Заблокированный администратором — не то же самое, что удаляющийся."""
    user = _user("zabanen@example.invalid")
    user.is_active = False
    user.save(update_fields=["is_active"])

    resp = APIClient().post(
        reverse("auth-login"),
        {"email": "zabanen@example.invalid", "password": PASSWORD},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_other_members_keep_working_while_head_is_frozen():
    """Заморозка главы не должна выключать семью остальным.

    Владение передаётся только при стирании, поэтому все 30 дней отсрочки
    семьёй владеет замороженный аккаунт. Проверяем, что это ломает ровно то,
    что должно (действия главы), и ничего сверх.
    """
    head = _user("zamorozhennyy-glava@example.invalid")
    family = _family(head)
    member = _user("uchastnik@example.invalid")
    FamilyMember.objects.create(family=family, user=member)

    request_deletion(head)

    client = _auth(member)
    assert client.get(reverse("users-me")).status_code == 200
    assert client.get(reverse("family-detail")).status_code == 200


@pytest.mark.django_db
def test_cancel_returns_false_when_nothing_to_cancel():
    assert cancel_deletion(_user("nichego@example.invalid")) is False


# ─── публичная веб-форма ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_public_request_answers_the_same_for_unknown_email():
    """Форма без входа не должна работать проверкой «есть ли такой аккаунт»."""
    _user("est@example.invalid")
    client = APIClient()
    known = client.post(reverse("auth-account-deletion-request"), {"email": "est@example.invalid"}, format="json")
    unknown = client.post(reverse("auth-account-deletion-request"), {"email": "netu@example.invalid"}, format="json")
    assert known.status_code == unknown.status_code == 200
    assert known.data["detail"] == unknown.data["detail"]


@pytest.mark.django_db
def test_public_confirm_freezes_account():
    from apps.users.account_deletion import make_token

    user = _user("pismo@example.invalid")
    resp = APIClient().post(
        reverse("auth-account-deletion-confirm"),
        {"token": make_token(user)},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
def test_public_confirm_rejects_garbage_token():
    resp = APIClient().post(reverse("auth-account-deletion-confirm"), {"token": "poddelka"}, format="json")
    assert resp.status_code == 400
    assert resp.data["code"] == "invalid_token"


# ─── стирание ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_purge_transfers_family_to_remaining_member():
    head = _user("uhodit@example.invalid")
    family = _family(head)
    stays = _user("ostaetsya@example.invalid")
    FamilyMember.objects.create(family=family, user=stays)

    request_deletion(head)
    report = purge_user(head)

    family.refresh_from_db()
    assert family.owner_id == stays.id
    assert FamilyMember.objects.get(family=family, user=stays).role == FamilyMember.Role.HEAD
    assert report["families_transferred"] == 1
    assert report["families_deleted"] == 0
    assert not User.objects.filter(id=head.id).exists()


@pytest.mark.django_db
def test_purge_deletes_family_when_nobody_remains():
    alone = _user("posledniy@example.invalid")
    family = _family(alone)

    report = purge_user(alone)

    assert not Family.objects.filter(id=family.id).exists()
    assert report["families_deleted"] == 1


@pytest.mark.django_db
def test_managed_member_cannot_inherit_and_is_removed_with_family():
    """Ребёнок без своего входа не может стать владельцем семьи."""
    head = _user("roditel@example.invalid")
    family = _family(head)
    # Так их и заводит apps/family/views.py: без адреса и без пригодного пароля.
    child = User(name="Ребёнок", is_managed=True)
    child.set_unusable_password()
    child.save()
    FamilyMember.objects.create(family=family, user=child)

    report = purge_user(head)

    assert not Family.objects.filter(id=family.id).exists()
    assert not User.objects.filter(id=child.id).exists()
    assert report["managed_deleted"] == 1


@pytest.mark.django_db
def test_purge_keeps_payments_without_the_family():
    """Платёж — запись о сделке, её сверяют с ЮKassa. Уйти вместе с семьёй не должен."""
    alone = _user("platil@example.invalid")
    family = _family(alone)
    payment = Payment.objects.create(
        family=family,
        amount=Decimal("499.00"),
        status=Payment.Status.SUCCEEDED,
        payment_id="mg-accdel-test-1",
    )

    purge_user(alone)

    payment.refresh_from_db()
    assert payment.family_id is None
    assert payment.amount == Decimal("499.00")
    assert payment.payment_id == "mg-accdel-test-1"


@pytest.mark.django_db
def test_purge_does_not_touch_other_families():
    victim = _user("svoya@example.invalid")
    _family(victim, name="Своя")
    stranger = _user("chuzhaya@example.invalid")
    other = _family(stranger, name="Чужая")

    purge_user(victim)

    other.refresh_from_db()
    assert other.owner_id == stranger.id


# ─── команда по расписанию ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_command_is_dry_run_without_apply():
    from io import StringIO

    from django.core.management import call_command

    user = _user("srok@example.invalid")
    request_deletion(user)
    User.objects.filter(id=user.id).update(deletion_requested_at=timezone.now() - timedelta(days=GRACE_DAYS + 1))

    out = StringIO()
    call_command("purge_deleted_accounts", stdout=out)
    assert "Пробный прогон" in out.getvalue()
    assert User.objects.filter(id=user.id).exists()

    call_command("purge_deleted_accounts", "--apply", stdout=StringIO())
    assert not User.objects.filter(id=user.id).exists()


@pytest.mark.django_db
def test_scheduled_task_purges_and_spares():
    """Задача beat, в отличие от команды, удаляет сразу — но только просроченных."""
    from apps.users.tasks import purge_deleted_accounts

    overdue = _user("proshel-srok@example.invalid")
    request_deletion(overdue)
    User.objects.filter(id=overdue.id).update(deletion_requested_at=timezone.now() - timedelta(days=GRACE_DAYS + 1))

    fresh = _user("tolko-chto@example.invalid")
    request_deletion(fresh)

    untouched = _user("ne-udalyaetsya@example.invalid")

    totals = purge_deleted_accounts()

    assert totals["purged"] == 1
    assert not User.objects.filter(id=overdue.id).exists()
    assert User.objects.filter(id=fresh.id).exists()
    assert User.objects.filter(id=untouched.id).exists()


@pytest.mark.django_db
def test_command_spares_accounts_still_within_grace():
    from io import StringIO

    from django.core.management import call_command

    user = _user("eshe-ne-srok@example.invalid")
    request_deletion(user)
    User.objects.filter(id=user.id).update(deletion_requested_at=timezone.now() - timedelta(days=GRACE_DAYS - 1))

    call_command("purge_deleted_accounts", "--apply", stdout=StringIO())
    assert User.objects.filter(id=user.id).exists()
