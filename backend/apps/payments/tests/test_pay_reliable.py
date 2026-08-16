"""MG_PAYRELIABLE: оплата обязана превращаться в подписку ровно один раз.

Каждый тест здесь закрывает свою дыру боевого режима — ту, из-за которой
деньги списались бы, а подписка не включилась (или включилась бы дважды).
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.payments.activation import ActivationError, activate_payment
from apps.payments.models import Payment
from apps.payments.views import is_yookassa_ip
from apps.subscriptions.models import PlanOffer, Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="pay@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Премиум", "price": Decimal("299.00"), "period": "month", "is_active": True},
    )
    month = PlanOffer.objects.create(
        plan=plan, code="premium_month", title="Месяц", months=1, price=Decimal("299.00"), sort_order=10
    )
    year = PlanOffer.objects.create(
        plan=plan, code="premium_year", title="Год", months=12, price=Decimal("2990.00"), sort_order=20
    )
    return user, family, plan, month, year


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def remote(status="succeeded", value="299.00"):
    return {"id": "x", "status": status, "paid": status == "succeeded", "amount": {"value": value, "currency": "RUB"}}


def make_payment(family, offer, payment_id="pay-1"):
    return Payment.objects.create(
        family=family, offer=offer, amount=offer.price, status=Payment.Status.PENDING, payment_id=payment_id
    )


@pytest.mark.django_db
class TestInitiation:
    def test_платёж_записывается_до_оплаты(self, setup, settings):
        """Раньше строка появлялась только после успеха — сверять было не с чем."""
        user, family, _, month, _ = setup
        settings.PAYMENTS_STUB = True

        resp = api(user).post(
            reverse("subscription-subscribe"),
            {"offer_code": "premium_month", "return_url": "https://menugen.ru/subscriptions"},
            format="json",
        )

        assert resp.status_code == 200, resp.data
        payment = Payment.objects.get(payment_id=resp.data["payment_id"])
        assert payment.status == Payment.Status.PENDING
        assert payment.offer == month
        assert payment.amount == month.price

    def test_старые_сборки_с_plan_code_работают(self, setup, settings):
        """В установленных APK выбора периода нет — там уходит plan_code."""
        user, _, plan, month, _ = setup
        settings.PAYMENTS_STUB = True

        resp = api(user).post(
            reverse("subscription-subscribe"),
            {"plan_code": plan.code, "return_url": "https://menugen.ru/subscriptions"},
            format="json",
        )

        assert resp.status_code == 200, resp.data
        # без указания периода берём самый короткий
        assert Payment.objects.get(payment_id=resp.data["payment_id"]).offer == month

    def test_неизвестный_период_отклоняется(self, setup, settings):
        user, *_ = setup
        settings.PAYMENTS_STUB = True

        resp = api(user).post(
            reverse("subscription-subscribe"),
            {"offer_code": "premium_decade", "return_url": "https://menugen.ru/subscriptions"},
            format="json",
        )

        assert resp.status_code == 400


@pytest.mark.django_db
class TestActivation:
    def test_оплата_выдаёт_подписку_на_купленный_период(self, setup, settings):
        settings.PAYMENTS_STUB = False
        _, family, plan, _, year = setup
        make_payment(family, year, "pay-year")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote(value="2990.00")):
            activate_payment("pay-year")

        sub = Subscription.objects.get(family=family, plan=plan)
        assert sub.status == Subscription.Status.ACTIVE
        assert (sub.expires_at - timezone.now()).days > 360

    def test_повтор_уведомления_не_выдаёт_вторую_подписку(self, setup, settings):
        """ЮKassa повторяет уведомление, пока не получит 200."""
        settings.PAYMENTS_STUB = False
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-dup")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote()):
            activate_payment("pay-dup")
            first = Subscription.objects.get(family=family).expires_at
            activate_payment("pay-dup")

        assert Subscription.objects.filter(family=family).count() == 1
        assert Subscription.objects.get(family=family).expires_at == first

    def test_продление_не_сжигает_остаток(self, setup, settings):
        """Оплата за неделю до конца добавляет месяц К СРОКУ, а не с нуля."""
        settings.PAYMENTS_STUB = False
        _, family, plan, month, _ = setup
        until = timezone.now() + timedelta(days=7)
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=23),
            expires_at=until,
        )
        make_payment(family, month, "pay-ext")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote()):
            activate_payment("pay-ext")

        sub = Subscription.objects.get(family=family)
        assert sub.expires_at > until + timedelta(days=27)
        assert Subscription.objects.filter(family=family).count() == 1

    def test_неоплаченный_платёж_подписки_не_даёт(self, setup, settings):
        settings.PAYMENTS_STUB = False
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-pending")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote(status="pending")):
            activate_payment("pay-pending")

        assert not Subscription.objects.filter(family=family).exists()
        assert Payment.objects.get(payment_id="pay-pending").status == Payment.Status.PENDING

    def test_чужая_сумма_отклоняется(self, setup, settings):
        """Оплатили меньше выставленного — подписки нет."""
        settings.PAYMENTS_STUB = False
        _, family, _, _, year = setup
        make_payment(family, year, "pay-cheat")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote(value="1.00")):
            with pytest.raises(ActivationError):
                activate_payment("pay-cheat")

        assert not Subscription.objects.filter(family=family).exists()

    def test_неизвестный_платёж_не_ломает_обработку(self, db):
        assert activate_payment("нет-такого") is None
        assert activate_payment("") is None


@pytest.mark.django_db
class TestWebhook:
    def url(self):
        return reverse("payment-webhook-yookassa")

    def body(self, payment_id, event="payment.succeeded"):
        return {"event": event, "object": {"id": payment_id, "status": "succeeded"}}

    def test_телу_уведомления_не_верим(self, setup, settings):
        """Статус берём у ЮKassa по API — подделанное тело бесполезно."""
        settings.PAYMENTS_STUB = False
        settings.PAYMENTS_WEBHOOK_CHECK_IP = False
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-forged")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote(status="canceled")) as f:
            resp = APIClient().post(self.url(), self.body("pay-forged"), format="json")

        assert resp.status_code == 200
        f.assert_called_once_with("pay-forged")
        assert not Subscription.objects.filter(family=family).exists()

    def test_посторонний_адрес_отвергается(self, setup, settings):
        settings.PAYMENTS_WEBHOOK_CHECK_IP = True
        resp = APIClient().post(
            self.url(), self.body("pay-x"), format="json", REMOTE_ADDR="203.0.113.7"
        )

        assert resp.status_code == 403

    def test_адрес_юкассы_пропускается(self, setup, settings):
        settings.PAYMENTS_STUB = False
        settings.PAYMENTS_WEBHOOK_CHECK_IP = True
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-ok")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote()):
            resp = APIClient().post(
                self.url(), self.body("pay-ok"), format="json", REMOTE_ADDR="185.71.76.5"
            )

        assert resp.status_code == 200
        assert Subscription.objects.filter(family=family).exists()

    def test_сбой_сети_просит_повтор(self, setup, settings):
        """500 → ЮKassa повторит. 200 на сетевой сбой потерял бы платёж."""
        settings.PAYMENTS_STUB = False
        settings.PAYMENTS_WEBHOOK_CHECK_IP = False
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-net")

        with patch("apps.payments.activation.fetch_remote_payment", side_effect=OSError("нет связи")):
            resp = APIClient().post(self.url(), self.body("pay-net"), format="json")

        assert resp.status_code == 500

    def test_отмена_помечает_платёж(self, setup, settings):
        settings.PAYMENTS_WEBHOOK_CHECK_IP = False
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-cancel")

        resp = APIClient().post(self.url(), self.body("pay-cancel", "payment.canceled"), format="json")

        assert resp.status_code == 200
        assert Payment.objects.get(payment_id="pay-cancel").status == Payment.Status.CANCELLED


@pytest.mark.django_db
class TestStatusEndpoint:
    def test_возврат_с_оплаты_включает_подписку_без_уведомления(self, setup, settings):
        """Уведомление может опоздать — человек уже смотрит на экран."""
        settings.PAYMENTS_STUB = False
        user, family, _, month, _ = setup
        make_payment(family, month, "pay-return")

        with patch("apps.payments.activation.fetch_remote_payment", return_value=remote()):
            resp = api(user).get(reverse("payment-status", args=["pay-return"]))

        assert resp.status_code == 200
        assert resp.data["status"] == Payment.Status.SUCCEEDED
        assert Subscription.objects.filter(family=family).exists()

    def test_чужой_платёж_не_виден(self, setup, settings):
        _, family, _, month, _ = setup
        make_payment(family, month, "pay-alien")
        stranger = User.objects.create_user(email="alien@example.com", name="Чужой", password="pass1234")
        alien_family = Family.objects.create(owner=stranger)
        FamilyMember.objects.create(family=alien_family, user=stranger, role=FamilyMember.Role.HEAD)

        resp = api(stranger).get(reverse("payment-status", args=["pay-alien"]))

        assert resp.status_code == 404


class TestIpCheck:
    def test_диапазоны_юкассы(self):
        assert is_yookassa_ip("185.71.76.1")
        assert is_yookassa_ip("77.75.156.11")
        assert is_yookassa_ip("2a02:5180::1")

    def test_посторонние_адреса(self):
        assert not is_yookassa_ip("8.8.8.8")
        assert not is_yookassa_ip("185.71.78.1")
        assert not is_yookassa_ip("не-адрес")
        assert not is_yookassa_ip("")


def rows(resp):
    """Список из ответа: пагинация в проекте включена не везде одинаково."""
    data = resp.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.mark.django_db
class TestOffersApi:
    def test_периоды_отдаются_с_выгодой(self, setup):
        resp = APIClient().get(reverse("subscription-offers"))

        assert resp.status_code == 200
        by_code = {o["code"]: o for o in rows(resp)}
        assert by_code["premium_month"]["discount_percent"] == 0
        # 2990 против 299×12 = 3588 — примерно 17 %
        assert by_code["premium_year"]["discount_percent"] == 17
        assert Decimal(by_code["premium_year"]["price_per_month"]) < Decimal(by_code["premium_month"]["price"])

    def test_выключенный_период_не_показываем(self, setup):
        PlanOffer.objects.filter(code="premium_year").update(is_active=False)

        resp = APIClient().get(reverse("subscription-offers"))

        assert [o["code"] for o in rows(resp)] == ["premium_month"]


@pytest.mark.django_db
class TestReceipt:
    def test_чек_собирается_с_контактом_покупателя(self, settings):
        from apps.payments.yookassa_client import build_receipt

        settings.PAYMENTS_RECEIPT_ENABLED = True
        settings.PAYMENTS_RECEIPT_VAT_CODE = 1

        receipt = build_receipt(Decimal("299.00"), "Подписка MenuGen — Месяц", "user@example.com")

        assert receipt["customer"]["email"] == "user@example.com"
        assert receipt["items"][0]["amount"]["value"] == "299.00"
        assert receipt["items"][0]["vat_code"] == 1

    def test_без_контакта_чек_не_шлём(self, settings):
        """Отправить его некуда — ЮKassa отклонит платёж целиком."""
        from apps.payments.yookassa_client import build_receipt

        settings.PAYMENTS_RECEIPT_ENABLED = True

        assert build_receipt(Decimal("299.00"), "Подписка", None) is None

    def test_выключенные_чеки_не_собираются(self, settings):
        from apps.payments.yookassa_client import build_receipt

        settings.PAYMENTS_RECEIPT_ENABLED = False

        assert build_receipt(Decimal("299.00"), "Подписка", "user@example.com") is None
