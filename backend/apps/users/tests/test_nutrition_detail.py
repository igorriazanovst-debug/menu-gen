"""MG_NUTRIDETAIL: настройка подробности чисел в строке еды.

Настройка отображения, а не данных: сами числа у записи те же, меняется
только то, что из них видно. Живёт в профиле на сервере, потому что одна и
та же — для приложения и для веба: храни её на устройстве, и один и тот же
дневник выглядел бы на телефоне и в браузере по-разному.

Проверяется здесь то, на чём такие настройки ломаются молча: значение по
умолчанию (у всех, кто был до правки, оно же), что ручка его отдаёт и
принимает, и что мусор не сохраняется.

Названия и адреса выдуманные.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import Profile, User

pytestmark = pytest.mark.django_db


def _person(email="detail@example.com"):
    user = User.objects.create_user(email=email, password="x", name="Читатель")
    Profile.objects.create(user=user)
    return user


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_по_умолчанию_калории_и_бжу():
    """Не «кратко»: дневник заводят ради состава еды.

    Прятать БЖУ по умолчанию значит прятать ответ на главный вопрос. Это же
    значение достаётся всем, кто завёлся до появления настройки.
    """
    user = _person()

    assert user.profile.nutrition_detail == Profile.NutritionDetail.NORMAL


def test_настройка_видна_в_профиле():
    # Без этого клиент не узнает выбор человека и покажет своё умолчание.
    user = _person()

    r = _client(user).get(reverse("users-me"))

    assert r.data["profile"]["nutrition_detail"] == "normal"


def test_настройку_можно_сменить():
    user = _person()

    r = _client(user).patch(reverse("users-me"), {"profile": {"nutrition_detail": "short"}}, format="json")

    assert r.status_code == 200, r.data
    user.profile.refresh_from_db()
    assert user.profile.nutrition_detail == "short"


def test_подробный_режим_тоже_принимается():
    user = _person()

    _client(user).patch(reverse("users-me"), {"profile": {"nutrition_detail": "detailed"}}, format="json")

    user.profile.refresh_from_db()
    assert user.profile.nutrition_detail == "detailed"


def test_неизвестный_режим_не_сохраняется():
    # Иначе клиент получил бы значение, которого не умеет показывать, и
    # «настройка отображения» превратилась бы в пустой экран.
    user = _person()

    r = _client(user).patch(reverse("users-me"), {"profile": {"nutrition_detail": "всё и сразу"}}, format="json")

    assert r.status_code == 400
    user.profile.refresh_from_db()
    assert user.profile.nutrition_detail == "normal"


def test_смена_настройки_не_трогает_остальной_профиль():
    # PATCH профиля частичный: прислали одно поле — остальные на месте.
    user = _person()
    user.profile.calorie_target = 2000
    user.profile.meal_plan_type = "5"
    user.profile.save(update_fields=["calorie_target", "meal_plan_type"])

    _client(user).patch(reverse("users-me"), {"profile": {"nutrition_detail": "short"}}, format="json")

    user.profile.refresh_from_db()
    assert user.profile.calorie_target == 2000
    assert user.profile.meal_plan_type == "5"
