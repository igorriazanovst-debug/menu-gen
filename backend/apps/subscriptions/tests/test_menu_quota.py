"""Freemium-квота на генерацию меню.

Покрытие:
- хелперы квоты (лимит/учёт/сброс по месяцу, premium → безлимит);
- API генерации: free до лимита → 403 при превышении; premium без лимита;
- свои меню видны бесплатной семье;
- лимит участников free-семьи (1).
"""

import datetime
from decimal import Decimal

import pytest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.recipes.models import Recipe
from apps.subscriptions.models import MenuGenerationCounter, Subscription, SubscriptionPlan
from apps.subscriptions.quota import (
    can_generate_menu,
    menu_quota_limit,
    menu_quota_summary,
    menu_quota_used,
    try_consume_menu_generation,
)
from apps.users.models import User

FREE_LIMIT = 4


def _free_family(email="free@e.com"):
    """Бесплатная семья (без подписки)."""
    head = User.objects.create_user(email=email, name="U", password="x12345")
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _attach_premium(family):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": Decimal("0")}
    )
    now = timezone.now()
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=now - datetime.timedelta(days=1),
        expires_at=now + datetime.timedelta(days=30),
    )


def _seed_recipes(n=30):
    for i in range(n):
        Recipe.objects.create(
            title=f"Рецепт {i}",
            ingredients=[{"name": f"Ингред {i}", "quantity": "100", "unit": "г"}],
            steps=[{"text": "Шаг 1"}],
            nutrition={"calories": {"value": str(300 + i * 10), "unit": "ккал"}},
            categories=["Завтраки"],
            is_published=True,
        )


@pytest.mark.django_db
class TestQuotaHelpers:
    def test_free_limit_from_plan(self):
        family, _ = _free_family()
        assert menu_quota_limit(family) == FREE_LIMIT

    def test_premium_is_unlimited(self):
        family, _ = _free_family()
        _attach_premium(family)
        assert menu_quota_limit(family) is None
        # premium всегда может генерировать и счётчик не трогает
        for _ in range(FREE_LIMIT + 3):
            with transaction.atomic():
                assert try_consume_menu_generation(family) is True
        assert not MenuGenerationCounter.objects.filter(family=family).exists()

    def test_consume_until_limit(self):
        family, _ = _free_family()
        for i in range(FREE_LIMIT):
            with transaction.atomic():
                assert try_consume_menu_generation(family) is True, f"итерация {i}"
        with transaction.atomic():
            assert try_consume_menu_generation(family) is False
        assert menu_quota_used(family) == FREE_LIMIT

    def test_resets_on_new_month(self):
        family, _ = _free_family()
        for _ in range(FREE_LIMIT):
            with transaction.atomic():
                try_consume_menu_generation(family)
        # «перематываем» счётчик на прошлый месяц
        counter = MenuGenerationCounter.objects.get(family=family)
        counter.period_start = (counter.period_start - datetime.timedelta(days=40)).replace(day=1)
        counter.save()
        assert menu_quota_used(family) == 0
        assert can_generate_menu(family) is True
        with transaction.atomic():
            assert try_consume_menu_generation(family) is True
        assert menu_quota_used(family) == 1

    def test_summary_shape(self):
        family, _ = _free_family()
        summary = menu_quota_summary(family)
        assert summary["limit"] == FREE_LIMIT
        assert summary["used"] == 0
        assert "reset_at" in summary


@pytest.mark.django_db
class TestQuotaApi:
    def test_free_generates_until_limit_then_403(self):
        family, head = _free_family()
        _seed_recipes()
        c = APIClient()
        c.force_authenticate(head)

        for i in range(FREE_LIMIT):
            resp = c.post(reverse("menu-generate"), {"period_days": 1}, format="json")
            assert resp.status_code == 201, f"генерация {i}: {resp.status_code} {resp.data}"

        resp = c.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert resp.status_code == 403
        assert resp.data["code"] == "menu_quota_exceeded"
        assert "reset_at" in resp.data

    def test_premium_unlimited(self):
        family, head = _free_family(email="prem@e.com")
        _attach_premium(family)
        _seed_recipes()
        c = APIClient()
        c.force_authenticate(head)
        for i in range(FREE_LIMIT + 2):
            resp = c.post(reverse("menu-generate"), {"period_days": 1}, format="json")
            assert resp.status_code == 201, f"генерация {i}: {resp.status_code}"

    def test_free_can_view_own_menus(self):
        family, head = _free_family(email="view@e.com")
        _seed_recipes()
        c = APIClient()
        c.force_authenticate(head)
        gen = c.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert gen.status_code == 201
        menu_id = gen.data["id"]
        assert c.get(reverse("menu-list")).status_code == 200
        assert c.get(reverse("menu-detail", args=[menu_id])).status_code == 200


@pytest.mark.django_db
class TestFreeMemberLimit:
    def test_free_family_second_member_blocked(self):
        family, head = _free_family(email="fam@e.com")
        other = User.objects.create_user(email="o@e.com", name="O", password="x12345")
        c = APIClient()
        c.force_authenticate(head)
        resp = c.post(reverse("family-invite"), {"email": other.email}, format="json")
        assert resp.status_code == 403
        assert not FamilyMember.objects.filter(family=family, user=other).exists()
