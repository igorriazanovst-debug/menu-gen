"""MG-605.D — GET /api/v1/diary/stats/ новая вложенная структура.

Покрывает:
- структура ответа: {date, planned, actual, total}
- planned = записи с planned_menu_item IS NOT NULL
- actual = is_eaten=True ИЛИ planned_menu_item IS NULL
- запись plan+is_eaten=True → попадает И в planned, И в actual/total
- запись plan+is_eaten=False → только planned, не actual
- запись manual (planned_menu_item=None) → всегда actual, не planned
- запись manual+is_eaten=True → всегда actual
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


def _user(email):
    return User.objects.create_user(email=email, password="pwd12345!", name=email.split("@")[0])


def _premium_family(owner):
    fam = Family.objects.create(owner=owner)
    head = FamilyMember.objects.create(family=fam, user=owner, role=FamilyMember.Role.HEAD)
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=30),
    )
    return fam, head


def _recipe(kcal=300, p=10, f=5, c=50):
    return Recipe.objects.create(
        title="R",
        ingredients=[],
        steps=[],
        nutrition={
            "calories": {"value": str(kcal), "unit": "ккал"},
            "proteins": {"value": str(p), "unit": "г"},
            "fats": {"value": str(f), "unit": "г"},
            "carbs": {"value": str(c), "unit": "г"},
        },
        is_published=True,
    )


def _menu_item(family, recipe, member=None):
    menu = Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        period_days=1,
        start_date=date.today(),
        end_date=date.today(),
        status=Menu.Status.ACTIVE,
    )
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        member=member,
        meal_type="breakfast",
        meal_slot="breakfast",
        day_offset=0,
        quantity=Decimal("1"),
        component_role="other",
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestDiaryStatsNewShape:

    def test_response_shape(self, client):
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=100)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="breakfast",
            recipe=r,
            nutrition=r.nutrition,
            quantity=1,
            is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        assert resp.status_code == 200
        d = resp.data[0]
        assert set(d.keys()) == {"date", "planned", "actual", "total"}
        for bucket in ("planned", "actual", "total"):
            assert set(d[bucket].keys()) == {"calories", "proteins", "fats", "carbs"}

    def test_manual_entry_counts_in_actual(self, client):
        """Запись без planned_menu_item — даже без is_eaten — считается actual."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=200)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="snack",
            recipe=r,
            nutrition=r.nutrition,
            quantity=1,
            is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["actual"]["calories"] == 200.0
        assert d["total"]["calories"] == 200.0
        assert d["planned"]["calories"] == 0.0

    def test_planned_unchecked_only_in_planned(self, client):
        """Плановая запись без галочки → только в planned, не в actual."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=300)
        mi = _menu_item(fam, r, member=head)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="breakfast",
            recipe=r,
            nutrition=r.nutrition,
            quantity=1,
            planned_menu_item=mi,
            is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 300.0
        assert d["actual"]["calories"] == 0.0
        assert d["total"]["calories"] == 0.0

    def test_planned_eaten_in_both(self, client):
        """Плановая запись с галочкой → и в planned, и в actual/total."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=400, p=20, f=10, c=30)
        mi = _menu_item(fam, r, member=head)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="breakfast",
            recipe=r,
            nutrition=r.nutrition,
            quantity=1,
            planned_menu_item=mi,
            is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 400.0
        assert d["actual"]["calories"] == 400.0
        assert d["total"]["calories"] == 400.0
        assert d["actual"]["proteins"] == 20.0

    def test_quantity_scales_nutrition(self, client):
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=100)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="snack",
            recipe=r,
            nutrition=r.nutrition,
            quantity=Decimal("2.5"),
            is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["actual"]["calories"] == 250.0

    def test_mixed_day(self, client):
        """План 300 без галки + manual 100 → planned=300, actual=100, total=100."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r_plan = _recipe(kcal=300)
        r_manual = _recipe(kcal=100)
        mi = _menu_item(fam, r_plan, member=head)
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="breakfast",
            recipe=r_plan,
            nutrition=r_plan.nutrition,
            quantity=1,
            planned_menu_item=mi,
            is_eaten=False,
        )
        DiaryEntry.objects.create(
            member=head,
            date=date.today(),
            meal_type="snack",
            recipe=r_manual,
            nutrition=r_manual.nutrition,
            quantity=1,
            is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 300.0
        assert d["actual"]["calories"] == 100.0
        assert d["total"]["calories"] == 100.0
