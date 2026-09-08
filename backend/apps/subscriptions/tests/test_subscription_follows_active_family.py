"""MG_ONEFAMILY: подписка показывается по той семье, в которой человек сейчас.

Сбой, найденный на проде уже после выкатки (chat-84). Человек состоял в двух
семьях, переключился в ту, где оплачен премиум. Всё приложение показывало
премиум — и `/users/me/`, и доступ к разделам, — а страница «Подписка» упрямо
писала «Активный тариф: Бесплатный» со сроком чужой, собственной семьи.

Причина: у подписок была своя копия правила выбора семьи, десятая по счёту. Она
не знала про выбор человека и брала самое старое членство. Та же функция выбирает
семью при оплате и при активации промокода, поэтому цена ошибки не «неверная
надпись», а «деньги ушли не в ту семью».

Проверяется то, что видит человек: после переключения `/subscriptions/current/`
отвечает подпиской новой семьи, а после возврата к себе — снова своей.

Имена выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не семьи.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


def _family(owner, name):
    family = Family.objects.create(owner=owner, name=name)
    FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return family


def _plan(code, name, seats=5):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code=code,
        defaults={"name": name, "price": 0, "max_family_members": seats},
    )
    return plan


def _subscribe(family, code, name):
    return Subscription.objects.create(
        family=family,
        plan=_plan(code, name),
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=365),
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def person_in_two_families(db):
    """Своя семья на бесплатном тарифе и чужая с премиумом — случай с прода."""
    person = _user("uchastnik@example.test", "Участник")
    own = _family(person, "Семья Своя")
    _subscribe(own, "free", "Бесплатный")

    head = _user("glava@example.test", "Глава")
    rich = _family(head, "Семья С Премиумом")
    _subscribe(rich, "premium", "Премиум")
    FamilyMember.objects.create(family=rich, user=person, role=FamilyMember.Role.MEMBER)

    return person, own, rich


@pytest.mark.django_db
def test_current_subscription_follows_the_switch(client, person_in_two_families):
    person, own, rich = person_in_two_families
    client.force_authenticate(person)

    resp = client.get(reverse("subscription-current"))
    assert resp.status_code == 200
    assert resp.data["plan"]["code"] == "free"

    assert client.post(reverse("family-switch"), {"family_id": rich.id}, format="json").status_code == 200

    resp = client.get(reverse("subscription-current"))
    assert resp.status_code == 200
    # Ровно это и было сломано: страница «Подписка» показывала бесплатный тариф
    # своей семьи, пока всё остальное приложение работало в премиум-семье.
    assert resp.data["plan"]["code"] == "premium"


@pytest.mark.django_db
def test_switching_back_returns_own_subscription(client, person_in_two_families):
    person, own, rich = person_in_two_families
    client.force_authenticate(person)

    client.post(reverse("family-switch"), {"family_id": rich.id}, format="json")
    client.post(reverse("family-switch"), {"family_id": own.id}, format="json")

    resp = client.get(reverse("subscription-current"))
    assert resp.status_code == 200
    assert resp.data["plan"]["code"] == "free"


@pytest.mark.django_db
def test_me_and_subscription_page_agree(client, person_in_two_families):
    """Два экрана про одно и то же не должны расходиться.

    Человек видит признак премиума в двух местах: в шапке (из /users/me/) и на
    странице «Подписка». Пока они читали семью по-разному, один экран уверял, что
    премиум есть, а другой — что его нет.
    """
    person, own, rich = person_in_two_families
    client.force_authenticate(person)
    client.post(reverse("family-switch"), {"family_id": rich.id}, format="json")

    me = client.get(reverse("users-me")).data["subscription_status"]
    current = client.get(reverse("subscription-current")).data

    assert me["is_active_premium"] is True
    assert me["plan_code"] == current["plan"]["code"] == "premium"
