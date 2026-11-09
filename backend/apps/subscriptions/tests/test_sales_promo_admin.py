"""MG_SALES: активации промокодов — вторая половина продаж.

Через кассу продаётся не всё: у промокода есть «владелец ключа» и аккаунт,
который его выдал, то есть кодами торгуют мимо ЮKassa. Раздел отвечает на те
же вопросы, что и оплаты, но отдельно от них — сложить деньги с подарками
значит не ответить ни на один.

Названия и адреса выдуманные.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone

from apps.family.models import Family, FamilyMember
from apps.subscriptions.admin import PromoRedemptionAdmin
from apps.subscriptions.models import PromoCode, PromoRedemption, Subscription, SubscriptionPlan
from apps.users.models import User


def _staff():
    return User.objects.create_user(
        email="boss@example.com", password="x", name="Начальник", is_staff=True, is_superuser=True
    )


def _plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Премиум", "price": Decimal("399"), "period": "year"}
    )
    return plan


def _family(email, name, phone=None, members=1):
    owner = User.objects.create_user(email=email, password="x", name=name, phone=phone)
    family = Family.objects.create(name=f"Семья {name}", owner=owner)
    FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    for i in range(1, members):
        mate = User.objects.create_user(email=f"{i}-{email}", password="x", name=f"{name} {i}")
        FamilyMember.objects.create(family=family, user=mate, role=FamilyMember.Role.MEMBER)
    return family


def _code(code, *, issued_by=None, owner="", days=None, campaign=""):
    return PromoCode.objects.create(
        code=code,
        plan=_plan(),
        duration_days=days,
        max_redemptions=1,
        campaign=campaign,
        owner=owner,
        created_by=issued_by,
    )


def _redeem(promo, family, revoked=False):
    r = PromoRedemption.objects.create(promo=promo, family=family, user=family.owner)
    if revoked:
        r.revoked_at = timezone.now()
        r.revoke_mode = "free"
        r.save(update_fields=["revoked_at", "revoke_mode"])
    return r


def _admin():
    return PromoRedemptionAdmin(PromoRedemption, AdminSite())


def _rows(admin_obj, user):
    request = RequestFactory().get("/admin/subscriptions/promoredemption/")
    request.user = user
    response = admin_obj.changelist_view(request)
    return dict(response.context_data["sales_summary"])


@pytest.mark.django_db
class TestСводкаПромокодов:
    def test_считает_активации_и_семьи(self):
        staff = _staff()
        manager = User.objects.create_user(email="sales@example.com", password="x", name="Продажник")
        a = _family("a@example.com", "Анна")
        b = _family("b@example.com", "Борис")
        _redeem(_code("K1", issued_by=manager, owner="ООО Ромашка"), a)
        _redeem(_code("K2", issued_by=manager, owner="ООО Ромашка"), b)

        rows = _rows(_admin(), staff)

        assert rows["Активаций"] == "2"
        assert rows["Действует"] == "2"
        assert rows["Семей"] == "2"
        assert rows["Кодов задействовано"] == "2"

    def test_отозванные_не_считаются_действующими(self):
        staff = _staff()
        a = _family("a@example.com", "Анна")
        b = _family("b@example.com", "Борис")
        _redeem(_code("K1"), a)
        _redeem(_code("K2"), b, revoked=True)

        rows = _rows(_admin(), staff)

        assert rows["Активаций"] == "2"
        assert rows["Действует"] == "1"
        assert rows["Отозвано"] == "1"


@pytest.mark.django_db
class TestКолонкиПромокодов:
    def _row(self, promo, family):
        redemption = _redeem(promo, family)
        admin_obj = _admin()
        request = RequestFactory().get("/admin/subscriptions/promoredemption/")
        request.user = _staff()
        return admin_obj, admin_obj.get_queryset(request).get(pk=redemption.pk)

    def test_видно_под_каким_аккаунтом_выдан_код(self):
        # Ровно то, что просили: кодами торгуют мимо кассы, и без автора
        # выдачи непонятно, чья это продажа.
        manager = User.objects.create_user(email="sales@example.com", password="x", name="Продажник")
        admin_obj, row = self._row(_code("K1", issued_by=manager), _family("a@example.com", "Анна"))

        assert admin_obj.issued_by(row) == "sales@example.com"

    def test_у_старых_кодов_автор_не_записан_и_мы_этого_не_скрываем(self):
        # Писать «система» нельзя: это утверждение, а мы просто не знаем.
        admin_obj, row = self._row(_code("K1"), _family("a@example.com", "Анна"))

        assert admin_obj.issued_by(row) == "— не записано —"

    def test_владелец_ключа_показан(self):
        admin_obj, row = self._row(_code("K1", owner="ООО Ромашка"), _family("a@example.com", "Анна"))

        assert admin_obj.key_owner(row) == "ООО Ромашка"

    def test_клиент_и_размер_семьи(self):
        admin_obj, row = self._row(_code("K1"), _family("a@example.com", "Анна", phone="+79990000002", members=4))

        shown = admin_obj.customer(row)
        assert "Анна" in shown and "a@example.com" in shown
        assert admin_obj.phone(row) == "+79990000002"
        assert admin_obj.family_size(row) == 4

    def test_срок_из_своего_числа_дней(self):
        admin_obj, row = self._row(_code("K1", days=90), _family("a@example.com", "Анна"))

        assert admin_obj.term(row) == "90 дн"

    def test_без_своего_срока_берётся_период_тарифа(self):
        admin_obj, row = self._row(_code("K1"), _family("a@example.com", "Анна"))

        assert "период тарифа" in admin_obj.term(row)

    def test_срок_по_подписке_когда_она_есть(self):
        family = _family("a@example.com", "Анна")
        now = timezone.now()
        sub = Subscription.objects.create(
            family=family,
            plan=_plan(),
            status=Subscription.Status.ACTIVE,
            started_at=now,
            expires_at=now + timedelta(days=30),
        )
        redemption = PromoRedemption.objects.create(
            promo=_code("K1"), family=family, user=family.owner, subscription=sub
        )
        admin_obj = _admin()
        request = RequestFactory().get("/admin/subscriptions/promoredemption/")
        request.user = _staff()
        row = admin_obj.get_queryset(request).get(pk=redemption.pk)

        assert admin_obj.term(row) == "30 дн (по подписке)"
