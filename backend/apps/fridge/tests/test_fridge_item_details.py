"""Tests for GET /fridge/<id>/details/ — nutrition, days_left, usage_30d."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _family_with_premium():
    user = User.objects.create_user(email="t@t.t", password="x", name="T")
    family = Family.objects.create(name="F", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": "0", "period": "month"},
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user, family


def _auth(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
def test_details_product_null_returns_dashes():
    user, family = _family_with_premium()
    item = FridgeItem.objects.create(
        family=family,
        name="Молоко",
        quantity=1,
        unit="л",
        expiry_date=timezone.now().date() + datetime.timedelta(days=5),
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200, resp.content
    assert resp.data["item"]["name"] == "Молоко"
    assert resp.data["product"] is None
    assert resp.data["days_left"] == 5
    assert resp.data["usage_30d"]["count"] == 0


@pytest.mark.django_db
def test_details_with_product_nutrition_and_image():
    user, family = _family_with_premium()
    p = Product.objects.create(
        name="Молоко",
        barcode="111",
        calories_per_100g=Decimal("60"),
        nutrition={"proteins": 3, "fats": 2.5, "carbs": 4.7},
        image_url="https://example.org/milk.jpg",
    )
    item = FridgeItem.objects.create(
        family=family,
        product=p,
        name="Молоко",
        quantity=Decimal("1"),
        unit="л",
        expiry_date=timezone.now().date() + datetime.timedelta(days=3),
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200
    pd = resp.data["product"]
    assert pd is not None
    assert pd["image_url"] == "https://example.org/milk.jpg"
    assert pd["nutrition"]["proteins"] == 3
    assert resp.data["days_left"] == 3


@pytest.mark.django_db
def test_details_usage_30d_counts_exact_name():
    user, family = _family_with_premium()
    today = timezone.now().date()

    # Recipe that uses 'Молоко'
    recipe_milk = Recipe.objects.create(
        title="Каша",
        ingredients=[{"name": "Молоко", "quantity": "200", "unit": "мл"}],
        steps=[{"text": "Варить"}],
    )
    # Recipe with different name (should NOT match)
    recipe_other = Recipe.objects.create(
        title="Салат",
        ingredients=[{"name": "Огурец"}],
        steps=[],
    )
    # Recipe with 'молоко' lowercase — should MATCH (case-insensitive)
    recipe_milk2 = Recipe.objects.create(
        title="Блины",
        ingredients=[{"name": "молоко"}],
        steps=[],
    )

    # Menu within last 30 days
    menu_inside = Menu.objects.create(
        family=family,
        creator_id=user.id,
        period_days=7,
        start_date=today - datetime.timedelta(days=5),
        end_date=today + datetime.timedelta(days=2),
        status="active",
    )
    MenuItem.objects.create(
        menu=menu_inside, recipe=recipe_milk, meal_type="breakfast", meal_slot="breakfast", day_offset=0
    )
    MenuItem.objects.create(
        menu=menu_inside,
        recipe=recipe_milk2,
        meal_type="lunch",
        meal_slot="lunch",
        day_offset=1,
        component_role="grain",
    )
    MenuItem.objects.create(
        menu=menu_inside,
        recipe=recipe_other,
        meal_type="dinner",
        meal_slot="dinner",
        day_offset=2,
        component_role="vegetable",
    )

    # Menu OUTSIDE 30-day window — should NOT count
    menu_outside = Menu.objects.create(
        family=family,
        creator_id=user.id,
        period_days=7,
        start_date=today - datetime.timedelta(days=60),
        end_date=today - datetime.timedelta(days=53),
        status="archived",
    )
    MenuItem.objects.create(
        menu=menu_outside, recipe=recipe_milk, meal_type="breakfast", meal_slot="breakfast", day_offset=0
    )

    item = FridgeItem.objects.create(
        family=family,
        name="Молоко",
        quantity=1,
        unit="л",
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200
    usage = resp.data["usage_30d"]
    # 2 matches inside the window: recipe_milk + recipe_milk2 (case-insensitive)
    assert usage["count"] == 2, usage
    assert usage["period_days"] == 30
    titles = {r["title"] for r in usage["recipes"]}
    assert titles == {"Каша", "Блины"}, titles


@pytest.mark.django_db
def test_details_404_for_other_family_item():
    _, family_a = _family_with_premium()
    item = FridgeItem.objects.create(
        family=family_a,
        name="X",
        quantity=1,
        unit="шт",
    )
    # different user
    other_user = User.objects.create_user(email="o@o.o", password="x", name="O")
    other_family = Family.objects.create(name="OF", owner=other_user)
    FamilyMember.objects.create(family=other_family, user=other_user, role="head")
    plan = SubscriptionPlan.objects.get(code="premium")
    Subscription.objects.create(
        family=other_family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )

    c = _auth(other_user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 404
