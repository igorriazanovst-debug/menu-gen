"""MG_HEADKEEPS: глава семьи ведёт дневник участника, и видно, что это он.

Зачем. Ребёнок дневник сам не ведёт, у пожилого не всегда получается — и
раньше единственным выходом было отдать свой пароль. Теперь глава семьи вносит
запись за участника, но запись принадлежит участнику и помечена тем, кто её
внёс: клиент рисует рядом корону.

Где проходит граница. Добавлять — глава может всегда. Править и удалять чужое —
только с разрешения участника (галочка в его профиле) или если участник
несовершеннолетний. Разрешение даёт сам участник: согласие, которое глава может
выдать себе сам, ни от чего не защищает.

Проверяется поведение через ручки — то, что увидит человек, — плюс само правило
из access.py на границах (день рождения, неизвестный год, чужая семья).

Имена и даты выдуманные: посевной каталог продуктов (миграция fridge 0004)
семей и дневников не заводит.
"""

import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.access import can_add_for, can_edit_of, is_minor
from apps.diary.models import BodyMeasurement, DiaryEntry, WaterLog, WeightLog
from apps.family.models import Family, FamilyMember
from apps.users.models import Profile, User

TODAY = datetime.date.today()


def _user(email, name, *, birth_year=None, consent=False):
    user = User.objects.create_user(email=email, name=name, password="pwd12345!")
    Profile.objects.update_or_create(
        user=user,
        defaults={"birth_year": birth_year, "head_may_edit_diary": consent},
    )
    user.refresh_from_db()
    return user


def _family(owner, name):
    family = Family.objects.create(owner=owner, name=name)
    head = FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return family, head


def _join(family, user):
    return FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.MEMBER)


@pytest.fixture
def household(db):
    """Глава, взрослый участник без согласия и участник-ребёнок."""
    head_user = _user("glava@example.test", "Глава", birth_year=1980)
    family, head = _family(head_user, "Семья Проверочная")
    adult = _join(family, _user("vzrosly@example.test", "Взрослый", birth_year=1995))
    child = _join(family, _user("rebenok@example.test", "Ребёнок", birth_year=TODAY.year - 10))
    return {"family": family, "head": head, "adult": adult, "child": child}


@pytest.fixture
def client():
    return APIClient()


class TestAddingForSomeoneElse:
    """Внести запись за участника глава может всегда — она помечена короной."""

    def test_head_adds_diary_entry_to_member(self, client, household):
        client.force_authenticate(household["head"].user)

        resp = client.post(
            reverse("diary-list") + f"?member_id={household['adult'].id}",
            {"date": str(TODAY), "meal_slot": "lunch", "custom_name": "Суп проверочный", "nutrition": {}},
            format="json",
        )

        assert resp.status_code == 201
        entry = DiaryEntry.objects.get(pk=resp.data["id"])
        # Запись — участника, автор — глава. Это и есть вся суть задачи.
        assert entry.user_id == household["adult"].user_id
        assert entry.added_by_id == household["head"].user_id
        assert resp.data["added_by_name"] == "Глава"

    def test_own_entry_has_no_author(self, client, household):
        """Пустое поле значит «внёс сам» — короны у своей записи быть не должно."""
        client.force_authenticate(household["adult"].user)

        resp = client.post(
            reverse("diary-list"),
            {"date": str(TODAY), "meal_slot": "dinner", "custom_name": "Каша проверочная", "nutrition": {}},
            format="json",
        )

        assert resp.status_code == 201
        assert resp.data["added_by"] is None
        assert resp.data["added_by_name"] is None

    def test_member_cannot_add_for_another_member(self, client, household):
        client.force_authenticate(household["adult"].user)

        resp = client.post(
            reverse("diary-list") + f"?member_id={household['child'].id}",
            {"date": str(TODAY), "meal_slot": "lunch", "custom_name": "Чужое", "nutrition": {}},
            format="json",
        )

        assert resp.status_code == 403
        assert not DiaryEntry.objects.filter(user_id=household["child"].user_id).exists()

    def test_head_adds_water(self, client, household):
        client.force_authenticate(household["head"].user)

        resp = client.post(
            reverse("diary-water") + f"?member_id={household['child'].id}",
            {"date": str(TODAY), "water_ml": 500},
            format="json",
        )

        assert resp.status_code == 200
        log = WaterLog.objects.get(user_id=household["child"].user_id, date=TODAY)
        assert log.water_ml == 500
        assert log.added_by_id == household["head"].user_id

    def test_member_fixing_own_water_clears_the_crown(self, client, household):
        """Вода на день одна: поправил сам — корона уходит, значение снова его."""
        client.force_authenticate(household["head"].user)
        client.post(
            reverse("diary-water") + f"?member_id={household['adult'].id}",
            {"date": str(TODAY), "water_ml": 500},
            format="json",
        )

        client.force_authenticate(household["adult"].user)
        resp = client.post(reverse("diary-water"), {"date": str(TODAY), "water_ml": 1200}, format="json")

        assert resp.status_code == 200
        assert resp.data["added_by"] is None
        assert WaterLog.objects.get(user_id=household["adult"].user_id, date=TODAY).water_ml == 1200

    def test_head_adds_weight(self, client, household):
        client.force_authenticate(household["head"].user)

        resp = client.post(
            reverse("diary-weight") + f"?member_id={household['child'].id}",
            {"date": str(TODAY), "weight_kg": "35.4"},
            format="json",
        )

        assert resp.status_code == 200
        log = WeightLog.objects.get(user_id=household["child"].user_id, date=TODAY)
        assert log.added_by_id == household["head"].user_id

    def test_head_adds_measurements(self, client, household):
        client.force_authenticate(household["head"].user)

        resp = client.post(
            reverse("diary-measurements") + f"?member_id={household['child'].id}",
            {"date": str(TODAY), "waist_cm": "60.5"},
            format="json",
        )

        assert resp.status_code == 200
        row = BodyMeasurement.objects.get(user_id=household["child"].user_id, date=TODAY)
        assert str(row.waist_cm) == "60.5"
        assert row.added_by_id == household["head"].user_id


class TestEditingSomeoneElse:
    """Править чужое — только по разрешению или у несовершеннолетнего."""

    def _entry_of(self, member):
        return DiaryEntry.objects.create(
            user=member.user,
            member=member,
            date=TODAY,
            meal_type=DiaryEntry.MealType.LUNCH,
            custom_name="Своя запись",
            nutrition={},
        )

    def test_adult_without_consent_is_protected(self, client, household):
        entry = self._entry_of(household["adult"])
        client.force_authenticate(household["head"].user)

        resp = client.patch(
            reverse("diary-entry-detail", args=[entry.id]), {"custom_name": "Переписано"}, format="json"
        )

        assert resp.status_code == 403
        entry.refresh_from_db()
        assert entry.custom_name == "Своя запись"

    def test_adult_with_consent_may_be_edited(self, client, household):
        adult = household["adult"]
        adult.user.profile.head_may_edit_diary = True
        adult.user.profile.save(update_fields=["head_may_edit_diary"])
        entry = self._entry_of(adult)
        client.force_authenticate(household["head"].user)

        resp = client.patch(reverse("diary-entry-detail", args=[entry.id]), {"custom_name": "Уточнено"}, format="json")

        assert resp.status_code == 200
        entry.refresh_from_db()
        assert entry.custom_name == "Уточнено"

    def test_child_needs_no_consent(self, client, household):
        entry = self._entry_of(household["child"])
        client.force_authenticate(household["head"].user)

        resp = client.patch(reverse("diary-entry-detail", args=[entry.id]), {"custom_name": "Уточнено"}, format="json")

        assert resp.status_code == 200

    def test_head_may_delete_what_the_head_added(self, client, household):
        """Свою же запись глава убирает и без согласия: ошибся — исправил."""
        client.force_authenticate(household["head"].user)
        created = client.post(
            reverse("diary-list") + f"?member_id={household['adult'].id}",
            {"date": str(TODAY), "meal_slot": "lunch", "custom_name": "Ошибка", "nutrition": {}},
            format="json",
        )
        entry_id = created.data["id"]

        resp = client.delete(reverse("diary-entry-detail", args=[entry_id]))

        # Разрешения на чужое у главы нет, но эту строку внёс он сам: иначе его
        # же ошибка осталась бы в чужом дневнике навсегда.
        assert resp.status_code == 204
        assert not DiaryEntry.objects.filter(pk=entry_id).exists()

    def test_member_never_edits_another_member(self, client, household):
        entry = self._entry_of(household["child"])
        client.force_authenticate(household["adult"].user)

        resp = client.patch(reverse("diary-entry-detail", args=[entry.id]), {"custom_name": "Чужое"}, format="json")

        assert resp.status_code in (403, 404)


class TestTheRuleItself:
    """Границы правила — там, где оно чаще всего и ошибётся."""

    def test_unknown_birth_year_counts_as_adult(self, db):
        # Иначе неизвестный возраст открывал бы чужой дневник по умолчанию.
        user = _user("bezgoda@example.test", "Без года")
        assert is_minor(user) is False

    def test_birthday_year_counts_as_adult(self, db):
        user = _user("rovno18@example.test", "Ровно 18", birth_year=TODAY.year - 18)
        assert is_minor(user) is False

    def test_seventeen_is_minor(self, db):
        user = _user("semnadtsat@example.test", "Семнадцать", birth_year=TODAY.year - 17)
        assert is_minor(user) is True

    def test_head_of_another_family_may_do_nothing(self, db, household):
        stranger = _user("chuzhoy@example.test", "Чужой", birth_year=1990)
        _other, other_head = _family(stranger, "Семья Чужая")

        assert can_add_for(other_head, household["child"]) is False
        assert can_edit_of(other_head, household["child"]) is False

    def test_own_records_never_need_permission(self, db, household):
        adult = household["adult"]
        assert can_add_for(adult, adult) is True
        assert can_edit_of(adult, adult) is True


class TestConsentIsGivenByTheMember:
    """Согласие даёт участник. Глава себе его выдать не может."""

    def test_member_switches_it_in_own_profile(self, client, household):
        client.force_authenticate(household["adult"].user)

        resp = client.patch(reverse("users-me"), {"profile": {"head_may_edit_diary": True}}, format="json")

        assert resp.status_code == 200
        household["adult"].user.profile.refresh_from_db()
        assert household["adult"].user.profile.head_may_edit_diary is True

    def test_head_cannot_switch_it_for_the_member(self, client, household):
        client.force_authenticate(household["head"].user)

        client.patch(
            reverse("family-update-member", args=[household["adult"].id]),
            {"profile": {"head_may_edit_diary": True}},
            format="json",
        )

        household["adult"].user.profile.refresh_from_db()
        # Ручка семьи это поле не принимает: молча игнорирует или отвечает 400 —
        # важно лишь то, что согласие осталось не выданным.
        assert household["adult"].user.profile.head_may_edit_diary is False
