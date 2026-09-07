"""MG_OWNDIARY: дневник, вода и вес принадлежат человеку, а не месту за столом.

Что это чинит (chat-84). Все три таблицы ссылались на членство в семье, и из
этого следовали две беды.

Первая уже действовала: `FamilyMember` удалялся каскадом, значит исключение
человека из семьи стирало ему весь дневник, всю воду и все замеры веса. Человека
выводили из-за стола и заодно стирали историю его питания.

Вторая ждала переключения семей (T-26): у человека в двух семьях получались две
несвязанные истории, и при переходе его замеры веса пропадали бы с экрана.

Теперь владелец — `user`, а `member` остался пометкой «за каким столом записано»
и обнуляется при уходе. Из этого же следует граница видимости: свой дневник
человек видит целиком, а глава семьи — только то, что записано за его столом.

Названия выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не семьи и не дневники.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry, WaterLog, WeightLog
from apps.diary.views import _sync_profile_weight
from apps.family.models import Family, FamilyMember
from apps.users.models import Profile

User = get_user_model()


# ── помощники ────────────────────────────────────────────────────────────────


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


def _family(owner, name):
    family = Family.objects.create(owner=owner, name=name)
    head = FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return family, head


def _join(family, user):
    return FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.MEMBER)


def _entry(member, day, name):
    return DiaryEntry.objects.create(
        user=member.user,
        member=member,
        date=day,
        meal_type=DiaryEntry.MealType.LUNCH,
        custom_name=name,
        nutrition={"calories": {"value": 300}},
        quantity=1,
    )


@pytest.fixture
def client():
    return APIClient()


# ── главное: исключение из семьи больше не стирает историю ───────────────────


@pytest.mark.django_db
def test_removal_from_family_keeps_personal_history():
    """Раньше эта строка удаления уносила с собой весь дневник человека."""
    head = _user("glava@example.test", "Глава")
    family, _ = _family(head, "Семья Застольная")
    person = _user("uchastnik@example.test", "Участник")
    member = _join(family, person)

    today = date.today()
    _entry(member, today, "Суп проверочный")
    WaterLog.objects.create(user=person, member=member, date=today, water_ml=1500)
    WeightLog.objects.create(user=person, member=member, date=today, weight_kg=Decimal("70.5"))

    member.delete()

    assert DiaryEntry.objects.filter(user=person).count() == 1
    assert WaterLog.objects.filter(user=person).count() == 1
    assert WeightLog.objects.filter(user=person).count() == 1
    # Пометка «за каким столом» снята: в семейных отчётах записи больше не видны.
    assert DiaryEntry.objects.filter(user=person).first().member_id is None
    assert WaterLog.objects.filter(user=person).first().member_id is None
    assert WeightLog.objects.filter(user=person).first().member_id is None


@pytest.mark.django_db
def test_history_follows_the_person_between_families():
    """Записанное за одним столом видно и после перехода за другой."""
    person = _user("perehodyashchiy@example.test", "Переходящий")
    own, own_member = _family(person, "Семья Своя")

    other_head = _user("hozyain@example.test", "Хозяин")
    other, _ = _family(other_head, "Семья Чужая")
    other_member = _join(other, person)

    today = date.today()
    _entry(own_member, today, "Дома проверочное")
    _entry(other_member, today, "В гостях проверочное")

    names = set(DiaryEntry.objects.filter(user=person).values_list("custom_name", flat=True))
    assert names == {"Дома проверочное", "В гостях проверочное"}


@pytest.mark.django_db
def test_own_diary_shows_entries_made_in_another_family(client):
    """То же самое через API: человек видит свой дневник целиком."""
    person = _user("svoy@example.test", "Свой")
    own, own_member = _family(person, "Семья Своя")
    other_head = _user("drugoy@example.test", "Другой")
    other, _ = _family(other_head, "Семья Другая")
    other_member = _join(other, person)

    today = date.today()
    _entry(own_member, today, "Дома проверочное")
    _entry(other_member, today, "В гостях проверочное")

    client.force_authenticate(person)
    resp = client.get(reverse("diary-list"), {"date": str(today)})
    assert resp.status_code == 200
    assert {row["custom_name"] for row in resp.data["results"]} == {
        "Дома проверочное",
        "В гостях проверочное",
    }


@pytest.mark.django_db
def test_head_sees_only_what_was_recorded_at_their_table(client):
    """Граница приватности: чужая жизнь главе семьи не показывается.

    Глава смотрит дневник участника, чтобы понимать, как тот питается в их общей
    жизни. Записи, сделанные участником в другой семье, к этому столу отношения
    не имеют.
    """
    head = _user("glava2@example.test", "Глава")
    family, _ = _family(head, "Семья Наблюдаемая")
    person = _user("uchastnik2@example.test", "Участник")
    member = _join(family, person)

    outside_head = _user("snaruzhi@example.test", "Снаружи")
    outside, _ = _family(outside_head, "Семья Внешняя")
    outside_member = _join(outside, person)

    today = date.today()
    _entry(member, today, "За этим столом")
    _entry(outside_member, today, "За другим столом")

    client.force_authenticate(head)
    resp = client.get(reverse("diary-list"), {"date": str(today), "member_id": member.id})
    assert resp.status_code == 200
    assert [row["custom_name"] for row in resp.data["results"]] == ["За этим столом"]


# ── день у человека один ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_water_day_is_unique_per_person_not_per_membership():
    person = _user("voda@example.test", "Вода")
    own, own_member = _family(person, "Семья Водная")
    other_head = _user("hozyain2@example.test", "Хозяин")
    other, _ = _family(other_head, "Семья Гостевая")
    other_member = _join(other, person)

    today = date.today()
    WaterLog.objects.create(user=person, member=own_member, date=today, water_ml=1000)

    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        WaterLog.objects.create(user=person, member=other_member, date=today, water_ml=500)


@pytest.mark.django_db
def test_water_endpoint_returns_the_same_day_after_switching_family(client):
    """Вода за сегодня одна, из какой бы семьи её ни записали."""
    person = _user("voda2@example.test", "Вода два")
    own, own_member = _family(person, "Семья Водная-2")

    client.force_authenticate(person)
    today = str(date.today())
    resp = client.post(reverse("diary-water"), {"date": today, "water_ml": 1200}, format="json")
    assert resp.status_code == 200

    other_head = _user("hozyain3@example.test", "Хозяин")
    other, _ = _family(other_head, "Семья Гостевая-2")
    _join(other, person)

    resp = client.get(reverse("diary-water"), {"date": today})
    assert resp.status_code == 200
    assert resp.data["water_ml"] == 1200
    assert WaterLog.objects.filter(user=person, date=today).count() == 1


@pytest.mark.django_db
def test_profile_weight_takes_the_latest_measurement_of_the_person():
    """Вес в профиль берётся по человеку, а не по одному его членству."""
    person = _user("ves@example.test", "Вес")
    Profile.objects.create(user=person)
    own, own_member = _family(person, "Семья Весовая")
    other_head = _user("hozyain4@example.test", "Хозяин")
    other, _ = _family(other_head, "Семья Весовая-2")
    other_member = _join(other, person)

    today = date.today()
    WeightLog.objects.create(user=person, member=own_member, date=today - timedelta(days=3), weight_kg=Decimal("80.0"))
    WeightLog.objects.create(user=person, member=other_member, date=today, weight_kg=Decimal("78.0"))

    _sync_profile_weight(own_member)
    person.profile.refresh_from_db()
    assert person.profile.weight_kg == Decimal("78.0")


# ── совместимость: владелец выводится из членства ────────────────────────────


@pytest.mark.django_db
def test_owner_is_derived_from_membership_when_not_given():
    """Код, писавший только `member=`, продолжает создавать правильные строки."""
    person = _user("vyvod@example.test", "Вывод")
    family, member = _family(person, "Семья Выводная")

    entry = DiaryEntry.objects.create(
        member=member,
        date=date.today(),
        meal_type=DiaryEntry.MealType.BREAKFAST,
        custom_name="Каша проверочная",
        nutrition={},
        quantity=1,
    )
    water = WaterLog.objects.create(member=member, date=date.today(), water_ml=300)
    weight = WeightLog.objects.create(member=member, date=date.today(), weight_kg=Decimal("60.0"))

    assert entry.user_id == person.id
    assert water.user_id == person.id
    assert weight.user_id == person.id


@pytest.mark.django_db
def test_entry_stays_editable_by_its_author_after_leaving_the_family(client):
    """Своя запись остаётся своей и после ухода из семьи.

    Права раньше сверялись с членством: стоило человеку уйти, и собственную
    запись он не мог ни поправить, ни удалить.
    """
    head = _user("glava3@example.test", "Глава")
    family, _ = _family(head, "Семья Покидаемая")
    person = _user("ushedshiy@example.test", "Ушедший")
    member = _join(family, person)
    entry = _entry(member, date.today(), "Своё проверочное")

    own_family, _ = _family(person, "Семья Личная")
    member.delete()

    client.force_authenticate(person)
    resp = client.patch(reverse("diary-entry-detail", args=[entry.id]), {"custom_name": "Правленое"}, format="json")
    assert resp.status_code == 200
    entry.refresh_from_db()
    assert entry.custom_name == "Правленое"
