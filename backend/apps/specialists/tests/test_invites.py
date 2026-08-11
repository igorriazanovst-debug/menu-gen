"""MG_SPECINVITE: приглашение работает с двух сторон.

Со стороны клиента — по e-mail специалиста, и только на премиум-тарифе.
Со стороны специалиста — личным кодом: клиент вводит его, получает месяц
премиума, а специалист сразу получает доступ. Ввод кода и есть согласие
клиента, поэтому подтверждения не спрашиваем — но прекратить доступ клиент
должен уметь в любой момент, и это здесь тоже закреплено.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.specialists.invites import INVITE_DAYS, get_or_create_code, specialist_for_code
from apps.specialists.models import Specialist, SpecialistAssignment, SpecialistInviteCode
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def premium_plan(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": Decimal("0")}
    )
    return plan


def make_family(email, name="Клиент"):
    user = User.objects.create_user(email=email, password="pass12345", name=name)
    family = Family.objects.create(name=f"Семья {name}", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="adult")
    return family, user


def make_specialist(email, kind=Specialist.Type.DIETITIAN, verified=True):
    user = User.objects.create_user(email=email, password="pass12345", name=email.split("@")[0])
    return Specialist.objects.create(user=user, specialist_type=kind, is_verified=verified)


def give_premium(family, plan):
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=365),
    )


def api_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def has_premium(family):
    from apps.subscriptions.permissions import has_active_premium

    return has_active_premium(family)


@pytest.mark.django_db
class TestSpecialistCode:
    def test_код_выдаётся_и_не_меняется(self, premium_plan):
        spec = make_specialist("code@example.com")

        r1 = api_for(spec.user).get(reverse("specialist-invite-code"))
        r2 = api_for(spec.user).get(reverse("specialist-invite-code"))

        assert r1.status_code == 200, r1.data
        assert r1.data["code"] == r2.data["code"]
        assert r1.data["days"] == INVITE_DAYS
        assert SpecialistInviteCode.objects.count() == 1

    def test_неверифицированный_кода_не_получает(self, premium_plan):
        """Иначе кто угодно раздавал бы доступ к чужим данным."""
        spec = make_specialist("nover@example.com", verified=False)

        r = api_for(spec.user).get(reverse("specialist-invite-code"))

        assert r.status_code == 403
        assert not SpecialistInviteCode.objects.exists()

    def test_код_опознаётся_по_строке(self, premium_plan):
        spec = make_specialist("who@example.com")
        link = get_or_create_code(spec)

        assert specialist_for_code(link.promo.code) == spec
        assert specialist_for_code(link.promo.code.lower()) == spec
        assert specialist_for_code("НЕ-КОД") is None
        assert specialist_for_code("") is None


@pytest.mark.django_db
class TestRedeemCode:
    def redeem(self, user, code):
        return api_for(user).post(reverse("subscription-promo-redeem"), {"code": code}, format="json")

    def test_клиент_получает_премиум_и_специалиста(self, premium_plan):
        spec = make_specialist("diet@example.com")
        link = get_or_create_code(spec)
        family, user = make_family("client1@example.com")

        r = self.redeem(user, link.promo.code)

        assert r.status_code == 200, r.data
        assert has_premium(family)
        assignment = SpecialistAssignment.objects.get(family=family, specialist=spec)
        assert assignment.status == SpecialistAssignment.Status.ACTIVE
        assert assignment.specialist_type == Specialist.Type.DIETITIAN

    def test_ответ_называет_специалиста_прямо(self, premium_plan):
        """Клиент должен понять, что открыл доступ, из самого ответа."""
        spec = make_specialist("diet2@example.com")
        link = get_or_create_code(spec)
        _, user = make_family("client2@example.com")

        r = self.redeem(user, link.promo.code)

        assert "доступ к вашим данным открыт" in r.data["detail"]
        assert r.data["specialist"]["type"] == Specialist.Type.DIETITIAN

    def test_обычный_промокод_никого_не_привязывает(self, premium_plan):
        from apps.subscriptions.models import PromoCode

        PromoCode.objects.create(code="PLAIN-CODE", plan=premium_plan, duration_days=30)
        family, user = make_family("client3@example.com")

        r = self.redeem(user, "PLAIN-CODE")

        assert r.status_code == 200
        assert has_premium(family)
        assert not SpecialistAssignment.objects.filter(family=family).exists()
        assert "specialist" not in r.data

    def test_повторный_ввод_того_же_кода_отклоняется(self, premium_plan):
        spec = make_specialist("diet3@example.com")
        link = get_or_create_code(spec)
        _, user = make_family("client4@example.com")
        self.redeem(user, link.promo.code)

        r = self.redeem(user, link.promo.code)

        assert r.status_code == 400

    def test_вернувшийся_клиент_оживляет_доступ(self, premium_plan):
        """Доступ прекращали, потом клиент пришёл к тому же специалисту снова."""
        spec = make_specialist("diet4@example.com")
        link = get_or_create_code(spec)
        family, user = make_family("client5@example.com")
        SpecialistAssignment.objects.create(
            family=family,
            specialist=spec,
            specialist_type=spec.specialist_type,
            status=SpecialistAssignment.Status.ENDED,
        )

        self.redeem(user, link.promo.code)

        assert SpecialistAssignment.objects.get(family=family).status == SpecialistAssignment.Status.ACTIVE

    def test_код_многоразовый(self, premium_plan):
        spec = make_specialist("diet5@example.com")
        link = get_or_create_code(spec)
        _, first = make_family("c6@example.com", "Первый")
        _, second = make_family("c7@example.com", "Второй")

        assert self.redeem(first, link.promo.code).status_code == 200
        assert self.redeem(second, link.promo.code).status_code == 200
        assert SpecialistAssignment.objects.filter(specialist=spec).count() == 2


@pytest.mark.django_db
class TestInviteNeedsPremium:
    def test_без_премиума_приглашать_нельзя(self, premium_plan):
        make_specialist("diet6@example.com")
        family, user = make_family("free@example.com")

        r = api_for(user).post(reverse("specialist-invite"), {"email": "diet6@example.com"}, format="json")

        assert r.status_code == 403
        assert r.data["code"] == "premium_required"
        assert "код" in r.data["detail"]  # подсказываем путь без оплаты
        assert not SpecialistAssignment.objects.filter(family=family).exists()

    def test_с_премиумом_можно(self, premium_plan):
        make_specialist("diet7@example.com")
        family, user = make_family("paid@example.com")
        give_premium(family, premium_plan)

        r = api_for(user).post(reverse("specialist-invite"), {"email": "diet7@example.com"}, format="json")

        assert r.status_code == 201, r.data
        assert SpecialistAssignment.objects.get(family=family).status == SpecialistAssignment.Status.PENDING


@pytest.mark.django_db
class TestMySpecialists:
    def test_клиент_видит_кто_имеет_доступ(self, premium_plan):
        spec = make_specialist("cook@example.com", Specialist.Type.COOK)
        link = get_or_create_code(spec)
        family, user = make_family("client8@example.com")
        api_for(user).post(reverse("subscription-promo-redeem"), {"code": link.promo.code}, format="json")

        r = api_for(user).get(reverse("my-specialists"))

        assert r.status_code == 200
        row = r.data[0]
        assert row["specialist_email"] == "cook@example.com"
        assert row["role"] == Specialist.Type.COOK
        # объём доступа виден теми же словами, что и специалисту
        assert row["permissions"]["shopping"] == "write"
        assert row["permissions"]["diary"] == "none"

    def test_клиент_прекращает_доступ(self, premium_plan):
        spec = make_specialist("diet8@example.com")
        link = get_or_create_code(spec)
        family, user = make_family("client9@example.com")
        api_for(user).post(reverse("subscription-promo-redeem"), {"code": link.promo.code}, format="json")
        assignment = SpecialistAssignment.objects.get(family=family)

        r = api_for(user).post(reverse("assignment-end", args=[assignment.id]))

        assert r.status_code == 200
        assignment.refresh_from_db()
        assert assignment.status == SpecialistAssignment.Status.ENDED
        # и специалист сразу теряет доступ к данным
        spec_api = api_for(spec.user)
        assert spec_api.get(reverse("cabinet-client-menus", args=[family.id])).status_code in (403, 404)

    def test_завершённые_в_списке_не_висят(self, premium_plan):
        spec = make_specialist("diet9@example.com")
        family, user = make_family("client10@example.com")
        SpecialistAssignment.objects.create(
            family=family,
            specialist=spec,
            specialist_type=spec.specialist_type,
            status=SpecialistAssignment.Status.ENDED,
        )

        r = api_for(user).get(reverse("my-specialists"))

        assert r.data == []

    def test_без_семьи_список_пуст(self, premium_plan):
        user = User.objects.create_user(email="lonely@example.com", password="pass12345", name="Один")

        r = api_for(user).get(reverse("my-specialists"))

        assert r.status_code == 200
        assert r.data == []

    def test_чужие_специалисты_не_видны(self, premium_plan):
        spec = make_specialist("diet10@example.com")
        link = get_or_create_code(spec)
        _, mine = make_family("mine@example.com", "Мой")
        _, alien = make_family("alien@example.com", "Чужой")
        api_for(alien).post(reverse("subscription-promo-redeem"), {"code": link.promo.code}, format="json")

        r = api_for(mine).get(reverse("my-specialists"))

        assert r.data == []
