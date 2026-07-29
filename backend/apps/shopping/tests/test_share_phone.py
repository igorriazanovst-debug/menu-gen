"""MG_SHAREPHONE: шаринг списка покупок по номеру телефона."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family
from apps.shopping.models import ShoppingList, ShoppingListAccess
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner_with_list(db):
    owner = User.objects.create_user(email="owner@example.com", password="pass12345", name="Owner")
    _bootstrap_user(owner)
    family = Family.objects.get(owner=owner)
    sl = ShoppingList.objects.create(family=family, name="Покупки", created_by=owner)
    return owner, sl


@pytest.mark.django_db
class TestShareByPhone:
    def test_grant_by_phone(self, owner_with_list):
        owner, sl = owner_with_list
        client_user = User.objects.create_user(phone="+79990001122", password="pass12345", name="Client")

        api = APIClient()
        api.force_authenticate(owner)
        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"phone": "89990001122", "can_toggle": True},  # разный формат — должен нормализоваться
            format="json",
        )
        assert r.status_code == 201, r.data
        acc = ShoppingListAccess.objects.get(shopping_list=sl, user=client_user)
        assert acc.status == ShoppingListAccess.Status.PENDING
        assert acc.can_toggle is True

    def test_grant_by_phone_not_found(self, owner_with_list):
        owner, sl = owner_with_list
        api = APIClient()
        api.force_authenticate(owner)
        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"phone": "+70000000000"},
            format="json",
        )
        assert r.status_code == 400
        assert "phone" in r.data

    def test_grant_requires_some_identifier(self, owner_with_list):
        owner, sl = owner_with_list
        api = APIClient()
        api.force_authenticate(owner)
        r = api.post(reverse("shopping-list-access", args=[sl.id]), {}, format="json")
        assert r.status_code == 400
