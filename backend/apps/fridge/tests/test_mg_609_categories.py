"""MG-609: ProductCategory + endpoints (categories / products / history)."""
import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product, ProductCategory
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def premium_user(db):
    user = User.objects.create_user(email="u@u.u", password="x", name="U")
    fam = Family.objects.create(name="F", owner=user)
    FamilyMember.objects.create(family=fam, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": "0.00"},
    )
    Subscription.objects.create(
        family=fam, plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user, fam


@pytest.mark.django_db
class TestMg609Categories:
    def test_categories_seeded(self):
        assert ProductCategory.objects.filter(slug="dairy").exists()
        assert ProductCategory.objects.filter(slug="meat").exists()
        assert ProductCategory.objects.filter(slug="other").exists()

    def test_list_endpoint(self, client, premium_user):
        user, _ = premium_user
        client.force_authenticate(user)
        r = client.get(reverse("product-categories"))
        assert r.status_code == 200, r.content
        data = r.json()
        slugs = {row["slug"] for row in data}
        assert "dairy" in slugs and "meat" in slugs
        sort_orders = [row["sort_order"] for row in data]
        assert sort_orders == sorted(sort_orders)

    def test_seed_products_attached_to_categories(self):
        for slug in ("dairy", "meat", "vegetables", "eggs"):
            cat = ProductCategory.objects.get(slug=slug)
            assert cat.products.filter(is_seed=True).exists(), f"no seed products for {slug}"

    def test_products_list_filter_by_slug(self, client, premium_user):
        user, _ = premium_user
        client.force_authenticate(user)
        r = client.get(reverse("product-list"), {"category": "dairy", "seed": "1"})
        assert r.status_code == 200, r.content
        rows = r.json()
        assert len(rows) > 0
        for row in rows:
            assert row["category_slug"] == "dairy"
            assert row["is_seed"] is True

    def test_products_list_filter_by_id(self, client, premium_user):
        user, _ = premium_user
        cat = ProductCategory.objects.get(slug="meat")
        client.force_authenticate(user)
        r = client.get(reverse("product-list"), {"category": str(cat.id)})
        assert r.status_code == 200, r.content
        for row in r.json():
            assert row["category_id"] == cat.id

    def test_fridge_item_serializer_has_category_projections(self, client, premium_user):
        user, fam = premium_user
        dairy_milk = Product.objects.filter(is_seed=True, category_fk__slug="dairy", name="Молоко").first()
        assert dairy_milk is not None
        FridgeItem.objects.create(
            family=fam, product=dairy_milk, name="Молоко",
            quantity=1, unit="л",
            expiry_date=timezone.now().date() + datetime.timedelta(days=5),
            added_by_id=user.id,
        )
        client.force_authenticate(user)
        r = client.get(reverse("fridge-list"))
        assert r.status_code == 200, r.content
        rows = r.json()["results"]
        assert len(rows) == 1
        row = rows[0]
        assert row["product_category_slug"] == "dairy"
        assert row["product_category_name"] == "Молочные продукты"
        assert row["product_category_icon"] == "🥛"

    def test_history_aggregation(self, client, premium_user):
        user, fam = premium_user
        prod = Product.objects.filter(is_seed=True, name="Молоко").first()
        for _ in range(3):
            FridgeItem.objects.create(
                family=fam, product=prod, name="Молоко",
                quantity=1, unit="л", added_by_id=user.id,
            )
        FridgeItem.objects.create(family=fam, name="Грибы", quantity=200, unit="г", added_by_id=user.id)

        client.force_authenticate(user)
        r = client.get(reverse("fridge-history"))
        assert r.status_code == 200, r.content
        rows = r.json()
        names = [row["name"] for row in rows]
        assert "Молоко" in names and "Грибы" in names
        milk_row = next(r for r in rows if r["name"] == "Молоко")
        assert milk_row["times_used"] == 3
        assert milk_row["category_slug"] == "dairy"

    def test_history_isolated_per_family(self, client, premium_user):
        user, _ = premium_user
        other = User.objects.create_user(email="o@o.o", password="x", name="O")
        other_fam = Family.objects.create(name="OF", owner=other)
        FamilyMember.objects.create(family=other_fam, user=other, role="head")
        plan = SubscriptionPlan.objects.get(code="premium")
        Subscription.objects.create(
            family=other_fam, plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        FridgeItem.objects.create(family=other_fam, name="Сёмга", quantity=1, unit="кг",
                                  added_by_id=other.id)

        client.force_authenticate(user)
        r = client.get(reverse("fridge-history"))
        assert r.status_code == 200, r.content
        assert all(row["name"] != "Сёмга" for row in r.json())
