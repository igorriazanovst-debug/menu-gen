"""MG_WEIGHT2: вес с двумя знаками после запятой.

Жалоба с прода: «перестал записываться вес, вношу два знака после точки,
программа говорит что записан, а отображается только до 28.10».

Ничего не ломалось — ограничение в один знак стояло с самого начала
(миграция diary 0007, с тех пор не менялась). Человек просто стал переписывать
число с весов как есть, а бытовые весы дают шаг в пятьдесят граммов: 78.25.
Сервер такое отвергал, причём отвергал и «78.20», где ноль на конце не
добавляет никакой точности.

Отдельная подлость: отказ приходил полем `weight_kg`, а мобильное приложение
показывало общее «Не удалось сохранить вес» — человек читал это как «записано,
но не показывается» и искал поломку не там.

Названия и адреса выдуманные.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.models import WeightLog
from apps.diary.serializers import WeightLogSerializer
from apps.family.models import Family, FamilyMember
from apps.users.models import Profile

User = get_user_model()


def _person():
    user = User.objects.create_user(email="scale@example.com", password="x", name="Весовщик")
    Profile.objects.create(user=user, birth_year=1990)
    family = Family.objects.create(name="Семья", owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return user


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class TestРазборЗначения:
    """Сериализатор без базы: что принимается и во что превращается."""

    def _parse(self, raw):
        s = WeightLogSerializer(data={"date": "2026-11-02", "weight_kg": raw, "note": ""})
        return s, s.is_valid()

    def test_два_знака_принимаются(self):
        s, ok = self._parse("78.25")
        assert ok, s.errors
        assert s.validated_data["weight_kg"] == Decimal("78.25")

    def test_ноль_на_конце_больше_не_отказ(self):
        # Отвергать «78.20» — придирка: ноль на конце не добавляет точности.
        s, ok = self._parse("78.20")
        assert ok, s.errors

    def test_лишние_знаки_округляются_а_не_отвергаются(self):
        # Весы и импорт присылают что угодно. Отказ здесь означает потерянный
        # замер, а округление — потерянные полграмма.
        s, ok = self._parse("78.256")
        assert ok, s.errors
        assert s.validated_data["weight_kg"] == Decimal("78.26")

    def test_один_знак_и_целое_работают_как_раньше(self):
        for raw in ("78", "78.2"):
            s, ok = self._parse(raw)
            assert ok, (raw, s.errors)

    def test_границы_остались(self):
        # Округление не должно протащить бессмыслицу.
        assert not self._parse("0")[1]
        assert not self._parse("500.01")[1]
        assert not self._parse("-5")[1]


@pytest.mark.django_db
class TestЗаписьЧерезРучку:
    def test_записанное_с_двумя_знаками_возвращается_как_есть(self):
        user = _person()
        c = _client(user)

        r = c.post(reverse("diary-weight"), {"date": str(date.today()), "weight_kg": "78.25"}, format="json")

        assert r.status_code in (200, 201), r.data
        assert WeightLog.objects.get(user=user).weight_kg == Decimal("78.25")

        # И читается обратно тем же числом: человек должен увидеть то, что ввёл.
        got = c.get(reverse("diary-weight")).data
        assert [p["weight_kg"] for p in got] == ["78.25"]

    def test_профиль_принимает_столько_же_знаков(self):
        # Разная точность в двух местах про одно и то же — источник вечных
        # расхождений: в дневнике 78.25, в профиле 78.3.
        user = _person()
        c = _client(user)

        r = c.patch(reverse("users-me"), {"profile": {"weight_kg": "78.25"}}, format="json")

        assert r.status_code == 200, r.data
        user.profile.refresh_from_db()
        assert user.profile.weight_kg == Decimal("78.25")
