import hashlib
import hmac
import json
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
    user = User.objects.create_user(email="pay@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    plan = SubscriptionPlan.objects.create(
        code="premium", name="Premium", price="499.00", period="month", is_active=True
    )
    return user, family, plan


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.django_db
def test_webhook_payment_succeeded(client, setup, settings):
    _, family, plan = setup
    settings.YOOKASSA_SECRET_KEY = "test-secret"

    payload = {
        "event": "payment.succeeded",
        "object": {
            "id": "pay_abc123",
            "amount": {"value": "499.00", "currency": "RUB"},
            "metadata": {"family_id": family.id, "plan_code": plan.code},
        },
    }
    body = json.dumps(payload).encode()
    sig = _sign(body, "test-secret")

    resp = client.post(
        reverse("payment-webhook-yookassa"),
        data=body,
        content_type="application/json",
        HTTP_X_YOOKASSA_SIGNATURE=sig,
    )
    assert resp.status_code == 200
    assert Subscription.objects.filter(family=family, status="active").exists()
    assert Payment.objects.filter(family=family, status="succeeded").exists()


@pytest.mark.django_db
def test_webhook_invalid_signature(client, setup, settings):
    _, family, _ = setup
    settings.YOOKASSA_SECRET_KEY = "test-secret"
    body = b'{"event": "payment.succeeded"}'
    resp = client.post(
        reverse("payment-webhook-yookassa"),
        data=body,
        content_type="application/json",
        HTTP_X_YOOKASSA_SIGNATURE="bad-sig",
    )
    assert resp.status_code == 400
    assert not Subscription.objects.filter(family=family).exists()
