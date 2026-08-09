"""MG_SHAREERR: выдача доступа к списку покупок по e-mail.

Шаринг по телефону был покрыт тестами, по e-mail — нет, хотя это основной путь.
Заодно закреплено, что происходит с незнакомым адресом: доступ выдаётся только
зарегистрированным, и клиент должен показать именно эту причину.
"""

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


@pytest.fixture
def api(owner_with_list):
    owner, _ = owner_with_list
    client = APIClient()
    client.force_authenticate(owner)
    return client


@pytest.mark.django_db
class TestShareByEmail:
    def test_grant_by_email(self, owner_with_list, api):
        _, sl = owner_with_list
        target = User.objects.create_user(email="friend@example.com", password="pass12345", name="Friend")

        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"email": "friend@example.com", "can_toggle": True, "can_export": True},
            format="json",
        )

        assert r.status_code == 201, r.data
        acc = ShoppingListAccess.objects.get(shopping_list=sl, user=target)
        assert acc.status == ShoppingListAccess.Status.PENDING
        assert (acc.can_read, acc.can_toggle, acc.can_export) == (True, True, True)

    def test_email_case_does_not_matter(self, owner_with_list, api):
        _, sl = owner_with_list
        target = User.objects.create_user(email="friend@example.com", password="pass12345", name="Friend")

        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"email": "Friend@Example.COM"},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert ShoppingListAccess.objects.filter(shopping_list=sl, user=target).exists()

    def test_unknown_email_says_user_not_found(self, owner_with_list, api):
        _, sl = owner_with_list

        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"email": "nobody@example.com"},
            format="json",
        )

        assert r.status_code == 400
        assert "не найден" in str(r.data["email"][0]).lower()

    def test_empty_phone_alongside_email_is_ignored(self, owner_with_list, api):
        """Клиент может прислать оба поля — телефон пустым. Резолвим по e-mail."""
        _, sl = owner_with_list
        target = User.objects.create_user(email="friend@example.com", password="pass12345", name="Friend")

        r = api.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"email": "friend@example.com", "phone": ""},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert ShoppingListAccess.objects.filter(shopping_list=sl, user=target).exists()

    def test_stranger_cannot_share_someone_elses_list(self, owner_with_list):
        _, sl = owner_with_list
        stranger = User.objects.create_user(email="stranger@example.com", password="pass12345", name="S")
        _bootstrap_user(stranger)
        User.objects.create_user(email="friend@example.com", password="pass12345", name="Friend")

        client = APIClient()
        client.force_authenticate(stranger)
        r = client.post(
            reverse("shopping-list-access", args=[sl.id]),
            {"email": "friend@example.com"},
            format="json",
        )

        assert r.status_code == 404  # чужой список не виден вовсе
        assert not ShoppingListAccess.objects.filter(shopping_list=sl).exists()
