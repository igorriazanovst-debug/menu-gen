"""MG_SALES: раздел продаж в админке.

Проверяется то, ради чего раздел и заводили: сколько купили, кто купил и на
какой срок. Отдельно — что оплаты и промокоды не смешиваются: у первых деньги,
у вторых выдача, и одно число на двоих не отвечает ни на один вопрос.

Названия и адреса выдуманные.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone

from apps.family.models import Family, FamilyMember
from apps.payments.admin import PaymentAdmin
from apps.payments.models import Payment
from apps.subscriptions.models import PlanOffer, Subscription, SubscriptionPlan
from apps.users.models import User


def _staff():
    return User.objects.create_user(
        email="boss@example.com", password="x", name="Начальник", is_staff=True, is_superuser=True
    )


def _family(email, name, phone=None, members=1):
    owner = User.objects.create_user(email=email, password="x", name=name, phone=phone)
    family = Family.objects.create(name=f"Семья {name}", owner=owner)
    FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    for i in range(1, members):
        mate = User.objects.create_user(email=f"{i}-{email}", password="x", name=f"{name} {i}")
        FamilyMember.objects.create(family=family, user=mate, role=FamilyMember.Role.MEMBER)
    return family


def _plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Премиум", "price": Decimal("399"), "period": "month"}
    )
    return plan


def _offer(months, price, code):
    return PlanOffer.objects.create(plan=_plan(), code=code, title=f"{months} мес", months=months, price=Decimal(price))


def _paid(family, offer, amount, days_ago=0, status=Payment.Status.SUCCEEDED):
    return Payment.objects.create(
        family=family,
        offer=offer,
        amount=Decimal(amount),
        status=status,
        paid_at=timezone.now() - timedelta(days=days_ago),
    )


def _admin():
    return PaymentAdmin(Payment, AdminSite())


def _rows(admin_obj, user, query=""):
    """Сводка так, как её увидит человек: через настоящий changelist."""
    request = RequestFactory().get(f"/admin/payments/payment/{query}")
    request.user = user
    response = admin_obj.changelist_view(request)
    return dict(response.context_data["sales_summary"])


@pytest.mark.django_db
class TestСводкаОплат:
    def test_считает_покупки_выручку_и_покупателей(self):
        staff = _staff()
        month = _offer(1, "399", "m1")
        year = _offer(12, "3990", "y1")
        a = _family("a@example.com", "Анна")
        b = _family("b@example.com", "Борис")
        _paid(a, month, "399")
        _paid(a, year, "3990")
        _paid(b, month, "399")

        rows = _rows(_admin(), staff)

        assert rows["Куплено подписок"] == "3"
        assert rows["Выручка"] == "4 788 ₽"
        assert rows["Покупателей"] == "2"
        assert rows["Продано месяцев"] == "14"

    def test_неоплаченное_в_выручку_не_идёт(self):
        # «Ожидает» — это намерение, а не продажа. Сложить их значит
        # отчитаться о деньгах, которых нет.
        staff = _staff()
        month = _offer(1, "399", "m1")
        a = _family("a@example.com", "Анна")
        _paid(a, month, "399")
        _paid(a, month, "399", status=Payment.Status.PENDING)

        rows = _rows(_admin(), staff)

        assert rows["Куплено подписок"] == "1"
        assert rows["Выручка"] == "399 ₽"
        assert rows["Ждут оплаты"] == "1"

    def test_возвраты_показаны_отдельно(self):
        staff = _staff()
        month = _offer(1, "399", "m1")
        a = _family("a@example.com", "Анна")
        _paid(a, month, "399")
        _paid(a, month, "399", status=Payment.Status.REFUNDED)

        rows = _rows(_admin(), staff)

        assert rows["Куплено подписок"] == "1"
        assert rows["Возвраты"] == "1 на 399 ₽"

    def test_сводка_считается_по_текущему_отбору(self):
        # Это главное свойство: иначе фильтр менял бы список, но не числа над
        # ним, и два разных ответа спорили бы на одной странице.
        staff = _staff()
        month = _offer(1, "399", "m1")
        a = _family("a@example.com", "Анна")
        _paid(a, month, "399")
        _paid(a, month, "399", status=Payment.Status.REFUNDED)

        rows = _rows(_admin(), staff, "?status__exact=succeeded")

        assert rows["Куплено подписок"] == "1"
        assert "Возвраты" not in rows

    def test_повторные_покупки_видны(self):
        staff = _staff()
        month = _offer(1, "399", "m1")
        a = _family("a@example.com", "Анна")
        _paid(a, month, "399", days_ago=60)
        _paid(a, month, "399", days_ago=30)

        rows = _rows(_admin(), staff)

        assert rows["Покупок на покупателя"] == "2,00"


@pytest.mark.django_db
class TestКолонки:
    def _one(self, **kw):
        family = _family("a@example.com", "Анна", **kw)
        payment = _paid(family, _offer(12, "3990", "y1"), "3990")
        admin_obj = _admin()
        request = RequestFactory().get("/admin/payments/payment/")
        request.user = _staff()
        return admin_obj, admin_obj.get_queryset(request).get(pk=payment.pk)

    def test_клиент_показан_именем_и_адресом(self):
        admin_obj, row = self._one()

        shown = admin_obj.customer(row)

        assert "Анна" in shown
        assert "a@example.com" in shown

    def test_телефон_когда_есть(self):
        admin_obj, row = self._one(phone="+79990000001")

        assert admin_obj.phone(row) == "+79990000001"

    def test_телефона_нет_значит_прочерк(self):
        # Пустая ячейка читается как «не загрузилось». Прочерк — как «не
        # указан», и это разные вещи.
        admin_obj, row = self._one()

        assert admin_obj.phone(row) == "—"

    def test_размер_семьи(self):
        admin_obj, row = self._one(members=3)

        assert admin_obj.family_size(row) == 3

    def test_срок_берётся_из_оффера(self):
        admin_obj, row = self._one()

        assert "12 мес" in admin_obj.term(row)

    def test_без_оффера_срок_считается_по_подписке(self):
        # У старых платежей оффера нет вовсе. Выдумывать «месяц по умолчанию»
        # нельзя: годовую покупку это показало бы как месячную.
        family = _family("c@example.com", "Виктор")
        now = timezone.now()
        sub = Subscription.objects.create(
            family=family,
            plan=_plan(),
            status=Subscription.Status.ACTIVE,
            started_at=now - timedelta(days=365),
            expires_at=now,
        )
        payment = Payment.objects.create(
            family=family, subscription=sub, amount=Decimal("3990"), status=Payment.Status.SUCCEEDED, paid_at=now
        )
        admin_obj = _admin()
        request = RequestFactory().get("/admin/payments/payment/")
        request.user = _staff()
        row = admin_obj.get_queryset(request).get(pk=payment.pk)

        assert admin_obj.term(row) == "≈12 мес (из подписки)"

    def test_номер_покупки_не_зависит_от_фильтра(self):
        # Номер считается подзапросом, а не оконной функцией: оконная считала
        # бы уже после фильтра, и у второй покупки при отборе по месяцу номер
        # стал бы «первая».
        family = _family("d@example.com", "Галина")
        month = _offer(1, "399", "m1")
        _paid(family, month, "399", days_ago=60)
        second = _paid(family, month, "399", days_ago=1)

        admin_obj = _admin()
        request = RequestFactory().get("/admin/payments/payment/")
        request.user = _staff()
        row = admin_obj.get_queryset(request).filter(pk=second.pk).get()

        assert admin_obj.purchase_no(row) == 2
