"""MG_PAYSTUB: тесты тестового режима оплаты (заглушка ЮMoney)."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.payments.models import Payment
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="stub@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    plan = SubscriptionPlan.objects.create(
        code="premium", name="Premium", price="499.00", period="month", is_active=True
    )
    return user, family, plan


@pytest.mark.django_db
def test_subscribe_returns_stub_checkout_url(client, setup, settings):
    user, family, plan = setup
    settings.PAYMENTS_STUB = True
    client.force_authenticate(user)

    resp = client.post(
        reverse("subscription-subscribe"),
        {"plan_code": plan.code, "return_url": "https://menugen.ru/subscriptions?status=success"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "/api/v1/payments/stub/checkout/" in data["payment_url"]
    assert data["payment_id"].startswith("stub-")


@pytest.mark.django_db
def test_stub_confirm_activates_subscription(client, setup, settings):
    _, family, plan = setup
    settings.PAYMENTS_STUB = True

    url = reverse("payment-stub-confirm")
    resp = client.get(
        url,
        {
            "payment_id": "stub-test-1",
            "family_id": family.id,
            "plan_code": plan.code,
            "amount": "499.00",
            "return_url": "https://menugen.ru/subscriptions?status=success",
        },
    )
    assert resp.status_code == 302
    assert "payment=success" in resp["Location"]
    assert Subscription.objects.filter(family=family, status="active", plan=plan).exists()
    assert Payment.objects.filter(family=family, status="succeeded", payment_id="stub-test-1").exists()


@pytest.mark.django_db
def test_stub_confirm_idempotent(client, setup, settings):
    _, family, plan = setup
    settings.PAYMENTS_STUB = True
    params = {
        "payment_id": "stub-test-2",
        "family_id": family.id,
        "plan_code": plan.code,
        "amount": "499.00",
        "return_url": "https://menugen.ru/subscriptions",
    }
    client.get(reverse("payment-stub-confirm"), params)
    client.get(reverse("payment-stub-confirm"), params)  # повторный переход
    assert Subscription.objects.filter(family=family, plan=plan).count() == 1


@pytest.mark.django_db
def test_stub_disabled_returns_404(client, setup, settings):
    _, family, plan = setup
    settings.PAYMENTS_STUB = False
    resp = client.get(
        reverse("payment-stub-checkout"),
        {"payment_id": "x", "family_id": family.id, "plan_code": plan.code, "amount": "1", "return_url": "/"},
    )
    assert resp.status_code == 404
