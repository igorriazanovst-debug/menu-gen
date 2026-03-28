import datetime
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user_with_family(db):
    u = User.objects.create_user(email="fridge@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=u, name="Семья")
    FamilyMember.objects.create(family=family, user=u, role=FamilyMember.Role.HEAD)
    return u, family


@pytest.fixture
def fridge_item(db, user_with_family):
    _, family = user_with_family
    return FridgeItem.objects.create(
        family=family,
        name="Молоко",
        quantity=1,
        unit="л",
        expiry_date=datetime.date.today() + datetime.timedelta(days=3),
    )


@pytest.mark.django_db
class TestFridgeList:
    def test_list(self, client, user_with_family, fridge_item):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.get(reverse("fridge-list"))
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_list_expiring(self, client, user_with_family, fridge_item):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.get(reverse("fridge-list"), {"expiring_days": 5})
        assert resp.status_code == 200
        assert len(resp.data["results"]) >= 1

    def test_list_unauthenticated(self, client):
        resp = client.get(reverse("fridge-list"))
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFridgeCreate:
    def test_create(self, client, user_with_family):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("fridge-list"),
            {"name": "Яйца", "quantity": "10", "unit": "шт"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["name"] == "Яйца"

    def test_create_with_expiry(self, client, user_with_family):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("fridge-list"),
            {
                "name": "Кефир",
                "quantity": "0.5",
                "unit": "л",
                "expiry_date": str(datetime.date.today() + datetime.timedelta(days=7)),
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["expiry_date"] is not None

    def test_create_empty_name(self, client, user_with_family):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.post(reverse("fridge-list"), {"name": " "}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestFridgeItemDetail:
    def test_get(self, client, user_with_family, fridge_item):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.get(reverse("fridge-item-detail", args=[fridge_item.id]))
        assert resp.status_code == 200

    def test_patch(self, client, user_with_family, fridge_item):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.patch(
            reverse("fridge-item-detail", args=[fridge_item.id]),
            {"quantity": "2"},
            format="json",
        )
        assert resp.status_code == 200

    def test_soft_delete(self, client, user_with_family, fridge_item):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.delete(reverse("fridge-item-detail", args=[fridge_item.id]))
        assert resp.status_code == 204
        fridge_item.refresh_from_db()
        assert fridge_item.is_deleted is True


@pytest.mark.django_db
class TestBarcodeLookup:
    def test_found(self, client, user_with_family):
        user, _ = user_with_family
        Product.objects.create(name="Молоко Простоквашино", barcode="4601234567890")
        client.force_authenticate(user)
        resp = client.post(reverse("fridge-scan"), {"barcode": "4601234567890"}, format="json")
        assert resp.status_code == 200
        assert resp.data["name"] == "Молоко Простоквашино"

    def test_not_found(self, client, user_with_family):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.post(reverse("fridge-scan"), {"barcode": "0000000000000"}, format="json")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProductSearch:
    def test_search(self, client, user_with_family):
        user, _ = user_with_family
        Product.objects.create(name="Творог жирный")
        Product.objects.create(name="Творог обезжиренный")
        client.force_authenticate(user)
        resp = client.get(reverse("product-search"), {"q": "Творог"})
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_search_too_short(self, client, user_with_family):
        user, _ = user_with_family
        client.force_authenticate(user)
        resp = client.get(reverse("product-search"), {"q": "М"})
        assert resp.status_code == 200
        assert len(resp.data) == 0
