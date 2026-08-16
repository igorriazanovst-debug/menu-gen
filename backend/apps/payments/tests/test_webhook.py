"""Уведомление ЮKassa: подписка включается по факту оплаты.

MG_PAYRELIABLE. Здесь раньше проверялась HMAC-подпись тела на секретном ключе,
и тест это закреплял. Проверка была неверной: ЮKassa так уведомления не
подписывает, поэтому на боевых ключах отвергалось бы каждое настоящее
уведомление — деньги списаны, подписка не выдана.

Подпись заменена на два рубежа: адрес отправителя и, главное, перепроверка
платежа через API ЮKassa. Тесты этих рубежей — в test_pay_reliable.py; здесь
остался сквозной путь «уведомление → подписка».
"""

import json
from decimal import Decimal
from unittest.mock import patch

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
def setup(db, settings):
    settings.PAYMENTS_STUB = False
    settings.PAYMENTS_WEBHOOK_CHECK_IP = False
    user = User.objects.create_user(email="pay@example.com", name="Юзер", password="pass1234")
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


@pytest.mark.django_db
def test_webhook_payment_succeeded(client, setup):
    _, family, plan, offer = setup
    Payment.objects.create(
        family=family, offer=offer, amount=offer.price, status=Payment.Status.PENDING, payment_id="pay_abc123"
    )
    payload = {"event": "payment.succeeded", "object": {"id": "pay_abc123"}}
    remote = {"id": "pay_abc123", "status": "succeeded", "paid": True, "amount": {"value": "499.00"}}

    with patch("apps.payments.activation.fetch_remote_payment", return_value=remote):
        resp = client.post(
            reverse("payment-webhook-yookassa"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 200
    assert Subscription.objects.filter(family=family, plan=plan, status="active").exists()
    assert Payment.objects.filter(family=family, status="succeeded", payment_id="pay_abc123").exists()


@pytest.mark.django_db
def test_webhook_unknown_payment_is_not_an_error(client, setup):
    """Уведомление про чужой платёж: 200, но ничего не выдаём.

    Отвечать ошибкой нельзя — ЮKassa будет повторять его сутками.
    """
    _, family, _, _ = setup
    payload = {"event": "payment.succeeded", "object": {"id": "не-наш-платёж"}}

    with patch("apps.payments.activation.fetch_remote_payment", return_value={"status": "succeeded", "paid": True}):
        resp = client.post(
            reverse("payment-webhook-yookassa"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 200
    assert not Subscription.objects.filter(family=family).exists()


@pytest.mark.django_db
def test_webhook_broken_body(client, setup):
    resp = client.post(
        reverse("payment-webhook-yookassa"), data=b"{not json", content_type="application/json"
    )

    assert resp.status_code == 400
