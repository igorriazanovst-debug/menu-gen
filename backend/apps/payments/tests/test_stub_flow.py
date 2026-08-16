"""MG_PAYSTUB: тестовый режим оплаты (заглушка вместо ЮKassa).

Заглушка проходит ровно тот же путь активации, что и боевой платёж
(`activation.activate_payment`) — иначе она проверяла бы не то, что работает
на проде. Отличие одно: провайдера нет, «оплатил» решает кнопка на странице.
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.payments.models import Payment
from apps.subscriptions.models import PlanOffer, Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="stub@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("499.00"), "period": "month", "is_active": True},
    )
    offer = PlanOffer.objects.create(
        plan=plan, code="premium_month", title="Месяц", months=1, price=Decimal("499.00")
    )
    return user, family, plan, offer


def start_payment(client, user, offer, return_url="https://menugen.ru/subscriptions"):
    client.force_authenticate(user)
    resp = client.post(
        reverse("subscription-subscribe"),
        {"offer_code": offer.code, "return_url": return_url},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    return resp.json()


@pytest.mark.django_db
def test_subscribe_returns_stub_checkout_url(client, setup, settings):
    user, _, _, offer = setup
    settings.PAYMENTS_STUB = True

    data = start_payment(client, user, offer)

    assert "/api/v1/payments/stub/checkout/" in data["payment_url"]
    assert data["payment_id"].startswith("stub-")


@pytest.mark.django_db
def test_stub_confirm_activates_subscription(client, setup, settings):
    user, family, plan, offer = setup
    settings.PAYMENTS_STUB = True
    payment_id = start_payment(client, user, offer)["payment_id"]

    resp = client.get(
        reverse("payment-stub-confirm"),
        {"payment_id": payment_id, "return_url": "https://menugen.ru/subscriptions"},
    )

    assert resp.status_code == 302
    assert "payment=success" in resp["Location"]
    assert Subscription.objects.filter(family=family, status="active", plan=plan).exists()
    assert Payment.objects.filter(family=family, status="succeeded", payment_id=payment_id).exists()


@pytest.mark.django_db
def test_stub_confirm_idempotent(client, setup, settings):
    user, family, plan, offer = setup
    settings.PAYMENTS_STUB = True
    payment_id = start_payment(client, user, offer)["payment_id"]
    params = {"payment_id": payment_id, "return_url": "https://menugen.ru/subscriptions"}

    client.get(reverse("payment-stub-confirm"), params)
    client.get(reverse("payment-stub-confirm"), params)  # повторный переход

    assert Subscription.objects.filter(family=family, plan=plan).count() == 1


@pytest.mark.django_db
def test_stub_cancel_marks_payment(client, setup, settings):
    user, family, _, offer = setup
    settings.PAYMENTS_STUB = True
    payment_id = start_payment(client, user, offer)["payment_id"]

    resp = client.get(
        reverse("payment-stub-cancel"),
        {"payment_id": payment_id, "return_url": "https://menugen.ru/subscriptions"},
    )

    assert "payment=cancel" in resp["Location"]
    assert Payment.objects.get(payment_id=payment_id).status == Payment.Status.CANCELLED
    assert not Subscription.objects.filter(family=family).exists()


@pytest.mark.django_db
def test_stub_disabled_returns_404(client, setup, settings):
    settings.PAYMENTS_STUB = False

    resp = client.get(reverse("payment-stub-checkout"), {"payment_id": "x", "return_url": "/"})

    assert resp.status_code == 404
