"""MG_SHOPDEL: удалять позиции из списка может только владелец.

В мобильном удаление доступно долгим нажатием, и жест показывается лишь тем, у
кого есть права. Но клиент — не защита: право проверяется здесь.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.shopping.models import ShoppingList, ShoppingListAccess, ShoppingListItem
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def list_with_item(db):
    owner = User.objects.create_user(email="owner@example.com", password="pass12345", name="Owner")
    _bootstrap_user(owner)
    family = Family.objects.get(owner=owner)
    sl = ShoppingList.objects.create(family=family, name="Покупки", created_by=owner)
    item = ShoppingListItem.objects.create(shopping_list=sl, name="Молоко")
    return owner, family, sl, item


def url_for(sl, item):
    return reverse("shopping-item-detail", args=[sl.id, item.id])


@pytest.mark.django_db
class TestDeleteItem:
    def test_owner_deletes(self, list_with_item):
        owner, _, sl, item = list_with_item
        api = APIClient()
        api.force_authenticate(owner)

        r = api.delete(url_for(sl, item))

        assert r.status_code == 204
        assert not ShoppingListItem.objects.filter(id=item.id).exists()

    def test_family_member_cannot_delete(self, list_with_item):
        _, family, sl, item = list_with_item
        member = User.objects.create_user(email="member@example.com", password="pass12345", name="M")
        FamilyMember.objects.create(family=family, user=member, role=FamilyMember.Role.MEMBER)

        api = APIClient()
        api.force_authenticate(member)
        r = api.delete(url_for(sl, item))

        assert r.status_code == 403
        assert ShoppingListItem.objects.filter(id=item.id).exists()

    def test_shared_user_with_toggle_cannot_delete(self, list_with_item):
        """Доступ «может отмечать покупки» правом удаления не является."""
        _, _, sl, item = list_with_item
        guest = User.objects.create_user(email="guest@example.com", password="pass12345", name="G")
        ShoppingListAccess.objects.create(
            shopping_list=sl,
            user=guest,
            can_read=True,
            can_toggle=True,
            status=ShoppingListAccess.Status.ACCEPTED,
        )

        api = APIClient()
        api.force_authenticate(guest)
        r = api.delete(url_for(sl, item))

        assert r.status_code == 403
        assert ShoppingListItem.objects.filter(id=item.id).exists()

    def test_stranger_sees_nothing(self, list_with_item):
        _, _, sl, item = list_with_item
        stranger = User.objects.create_user(email="stranger@example.com", password="pass12345", name="S")
        _bootstrap_user(stranger)

        api = APIClient()
        api.force_authenticate(stranger)
        r = api.delete(url_for(sl, item))

        assert r.status_code == 404
        assert ShoppingListItem.objects.filter(id=item.id).exists()
