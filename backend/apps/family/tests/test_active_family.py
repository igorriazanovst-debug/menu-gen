"""MG_ACTIVEFAMILY: человек в нескольких семьях работает в одной, выбранной им.

Решение владельца (chat-84): состоять можно в нескольких семьях, но интерфейс в
каждый момент показывает одну. Переключение происходит по выбору человека — и
после принятия приглашения; обратный путь — переключиться на свою, при этом
чужая перестаёт отображаться до обратного переключения. При исключении из семьи
доступ теряется и остаётся своя.

Главное, что здесь проверяется, — переключение меняет разом ВСЕ разделы. Ради
этого в T-25 восемь копий правила сводили в одно место: если хоть одна точка
останется на прежней семье, человек получит холодильник одной семьи со списком
покупок другой, и это будет выглядеть как утечка чужих данных.

Имена выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не семьи.
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.family.selection import current_family, current_membership
from apps.family.views import _get_user_family as family_screen
from apps.fridge.views import _get_family as fridge
from apps.fridge.visibility import family_of as product_catalog
from apps.menu.views import _get_family as menu
from apps.payments.views import _get_family as payments
from apps.shopping.permissions import get_user_family as shopping
from apps.subscriptions.permissions import get_user_family as subscriptions
from apps.users.deletion_views import _family_of as account_deletion
from apps.users.models import User

FAMILY_RESOLVERS = [
    ("экран Семья", family_screen),
    ("холодильник", fridge),
    ("каталог продуктов", product_catalog),
    ("меню", menu),
    ("платежи", payments),
    ("подписка", subscriptions),
    ("покупки", shopping),
    ("удаление аккаунта", account_deletion),
]


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


def _family_with_head(user, name):
    family = Family.objects.create(owner=user, name=name)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return family


def _join(family, user):
    return FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.MEMBER)


def _answers(user):
    user.refresh_from_db()
    return {label: fn(user) for label, fn in FAMILY_RESOLVERS}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def two_families(db):
    """Человек со своей семьёй и членством в чужой — ровно случай из жизни."""
    person = _user("uchastnik@example.test", "Участник")
    own = _family_with_head(person, "Семья Своя")
    head = _user("glava@example.test", "Глава")
    invited = _family_with_head(head, "Семья Пригласившая")
    _join(invited, person)
    return person, own, invited


# ── переключение ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_without_a_choice_behaviour_is_unchanged(two_families):
    """Выбор не сделан — работает прежнее правило, самое старое членство."""
    person, own, invited = two_families
    assert set(_answers(person).values()) == {own}


@pytest.mark.django_db
def test_switch_moves_every_section_at_once(client, two_families):
    person, own, invited = two_families
    client.force_authenticate(person)

    resp = client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    assert resp.status_code == 200

    answers = _answers(person)
    assert set(answers.values()) == {invited}, answers
    assert current_membership(person).family_id == invited.id


@pytest.mark.django_db
def test_switch_back_to_own_family(client, two_families):
    person, own, invited = two_families
    client.force_authenticate(person)

    client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    resp = client.post(reverse("family-switch"), {"family_id": own.id}, format="json")
    assert resp.status_code == 200
    assert set(_answers(person).values()) == {own}


@pytest.mark.django_db
def test_cannot_switch_to_a_family_you_are_not_in(client, two_families):
    """Чужой стол не подтверждает даже своё существование."""
    person, own, invited = two_families
    stranger = _user("chuzhoy@example.test", "Чужой")
    alien = _family_with_head(stranger, "Семья Чужая")

    client.force_authenticate(person)
    resp = client.post(reverse("family-switch"), {"family_id": alien.id}, format="json")
    assert resp.status_code == 404
    assert set(_answers(person).values()) == {own}


@pytest.mark.django_db
def test_switch_requires_authentication(client, two_families):
    person, own, invited = two_families
    resp = client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    assert resp.status_code == 401


# ── потеря доступа ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_removal_returns_the_person_to_their_own_family(client, two_families):
    """Исключили — молча вернулись к себе, а не уткнулись в закрытую дверь."""
    person, own, invited = two_families
    client.force_authenticate(person)
    client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    assert set(_answers(person).values()) == {invited}

    FamilyMember.objects.get(family=invited, user=person).delete()

    answers = _answers(person)
    assert set(answers.values()) == {own}, answers
    person.refresh_from_db()
    # Указатель на семью без членства не доверяем и при чтении, но и висеть его
    # не оставляем — правда, снимает его ручка исключения, а не прямое удаление.
    assert current_family(person) == own


@pytest.mark.django_db
def test_remove_endpoint_clears_the_pointer(client, two_families):
    """Через ручку исключения указатель снимается сразу."""
    person, own, invited = two_families
    head = invited.owner
    member = FamilyMember.objects.get(family=invited, user=person)

    client.force_authenticate(person)
    client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")

    client.force_authenticate(head)
    resp = client.delete(reverse("family-remove-member", args=[member.id]))
    assert resp.status_code == 204

    person.refresh_from_db()
    assert person.active_family_id is None
    assert set(_answers(person).values()) == {own}


@pytest.mark.django_db
def test_person_can_leave_the_family_themselves(client, two_families):
    person, own, invited = two_families
    member = FamilyMember.objects.get(family=invited, user=person)

    client.force_authenticate(person)
    client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    resp = client.delete(reverse("family-remove-member", args=[member.id]))
    assert resp.status_code == 204

    person.refresh_from_db()
    assert person.active_family_id is None
    assert set(_answers(person).values()) == {own}


# ── список столов ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_choices_list_shows_both_families_and_marks_the_active_one(client, two_families):
    person, own, invited = two_families
    client.force_authenticate(person)

    resp = client.get(reverse("family-choices"))
    assert resp.status_code == 200
    by_id = {row["id"]: row for row in resp.data}
    assert set(by_id) == {own.id, invited.id}
    assert by_id[own.id]["is_active"] is True
    assert by_id[own.id]["is_own"] is True
    assert by_id[own.id]["role"] == FamilyMember.Role.HEAD
    assert by_id[invited.id]["is_active"] is False
    assert by_id[invited.id]["is_own"] is False
    assert by_id[invited.id]["role"] == FamilyMember.Role.MEMBER
    assert by_id[invited.id]["members_count"] == 2

    resp = client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    by_id = {row["id"]: row for row in resp.data}
    assert by_id[invited.id]["is_active"] is True
    assert by_id[own.id]["is_active"] is False


@pytest.mark.django_db
def test_premium_follows_the_table(client, two_families):
    """Премиум оплачивается за стол: за своим его нет, за приглашающим есть.

    Это то самое место, где переключение выглядит для человека неожиданно, и
    ради него в списке столов есть пометка has_premium — чтобы приложение могло
    предупредить до, а не показать пропажу после.
    """
    from apps.subscriptions.models import Subscription, SubscriptionPlan
    from apps.subscriptions.permissions import has_active_premium

    person, own, invited = two_families
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Премиум", "price": Decimal("0"), "period": SubscriptionPlan.Period.MONTH},
    )
    Subscription.objects.create(
        family=invited,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )

    client.force_authenticate(person)
    resp = client.get(reverse("family-choices"))
    by_id = {row["id"]: row for row in resp.data}
    assert by_id[own.id]["has_premium"] is False
    assert by_id[invited.id]["has_premium"] is True

    assert has_active_premium(current_family(person)) is False
    client.post(reverse("family-switch"), {"family_id": invited.id}, format="json")
    person.refresh_from_db()
    assert has_active_premium(current_family(person)) is True
