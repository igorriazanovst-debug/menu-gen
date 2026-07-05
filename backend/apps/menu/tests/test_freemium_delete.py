"""Регресс: free-юзер (без Premium) может удалять/восстанавливать свои меню.

Баг: MenuDeleteView и цикл карантина были закрыты IsFamilyPremiumOrReadOnly,
из-за чего бесплатная семья получала 403 на DELETE ещё до проверки прав.
Генерация меню free-юзерам уже открыта — удаление своих меню должно работать.
"""

import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import DeletedMenu, Menu
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


def _user(email="free@x.com", name="U", user_type="user"):
    return User.objects.create_user(email=email, name=name, password="x12345", user_type=user_type)


def _free_family(user, role=None):
    """Семья БЕЗ Premium-подписки (free-тариф)."""
    fam = Family.objects.create(owner=user, name=f"F {user.name}")
    FamilyMember.objects.create(family=fam, user=user, role=role or FamilyMember.Role.HEAD)
    return fam


def _menu(fam, creator):
    today = datetime.date.today()
    return Menu.objects.create(
        family=fam,
        creator_id=creator.id,
        period_days=1,
        start_date=today,
        end_date=today,
        status=Menu.Status.ACTIVE,
        filters_used={},
    )


@pytest.mark.django_db
class TestFreemiumDelete:
    def test_free_creator_can_delete_own_menu(self, client, db):
        # Главный кейс бага: free-юзер удаляет своё меню → 204, меню в карантине.
        head = _user(email="fd_del@x.com")
        fam = _free_family(head)
        menu = _menu(fam, head)
        client.force_authenticate(head)
        resp = client.delete(reverse("menu-delete", args=[menu.id]))
        assert resp.status_code == 204
        assert not Menu.objects.filter(id=menu.id).exists()
        assert DeletedMenu.objects.filter(family=fam, menu_id=menu.id).exists()

    def test_free_member_without_rights_gets_403(self, client, db):
        # Авторизация осталась: не создатель и не head → 403 (а не premium-гейт).
        head = _user(email="fd_h@x.com", name="HD")
        other = _user(email="fd_o@x.com", name="OT")
        fam = _free_family(head)
        FamilyMember.objects.create(family=fam, user=other, role=FamilyMember.Role.MEMBER)
        menu = _menu(fam, head)
        client.force_authenticate(other)
        resp = client.delete(reverse("menu-delete", args=[menu.id]))
        assert resp.status_code == 403
        assert Menu.objects.filter(id=menu.id).exists()

    def test_free_can_list_quarantine(self, client, db):
        # Карантин виден free-семье (200), не за premium-гейтом.
        head = _user(email="fd_q@x.com")
        _free_family(head)
        client.force_authenticate(head)
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 200

    def test_free_can_restore_own_menu(self, client, db):
        # Полный цикл: free-юзер удалил меню → может восстановить из карантина.
        head = _user(email="fd_re@x.com")
        fam = _free_family(head)
        menu = _menu(fam, head)
        client.force_authenticate(head)
        assert client.delete(reverse("menu-delete", args=[menu.id])).status_code == 204
        deleted = DeletedMenu.objects.get(family=fam, menu_id=menu.id)
        resp = client.post(reverse("menu-restore", args=[deleted.id]))
        assert resp.status_code == 201
        assert not DeletedMenu.objects.filter(id=deleted.id).exists()
