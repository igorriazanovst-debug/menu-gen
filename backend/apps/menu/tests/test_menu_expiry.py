"""MG_MENUEXPIRE: меню уходит в архив, когда календарный срок вышел.

Раньше меню оставалось `active` навсегда: статус меняла только кнопка «в
архив», которой ни в вебе, ни в приложении нет. В списке выбора копились
прошлогодние меню, и нужное приходилось искать среди них.

Проверяется то, что видит человек: просроченное пропадает из списка актуальных
и находится в архиве, а из базы никуда не девается. Отдельно — что список
верен и без ночной задачи: статус проставляет beat, но выдача не должна ждать
до утра.

Имена и даты выдуманные; посевной каталог продуктов (миграция fridge 0004)
здесь ни при чём — семьи и меню он не заводит.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu
from apps.menu.tasks import archive_expired_menus


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def family(db):
    from apps.users.models import User

    user = User.objects.create_user(email="glava@example.test", name="Глава", password="pwd12345!")
    fam = Family.objects.create(owner=user, name="Семья Проверочная")
    FamilyMember.objects.create(family=fam, user=user, role=FamilyMember.Role.HEAD)
    return fam


def _menu(family, *, ends_in_days, days=7, status=Menu.Status.ACTIVE):
    end = timezone.localdate() + datetime.timedelta(days=ends_in_days)
    return Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        start_date=end - datetime.timedelta(days=days - 1),
        end_date=end,
        period_days=days,
        status=status,
    )


def _ids(response):
    data = response.data
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return [row["id"] for row in rows]


class TestTheTask:
    def test_expired_menu_goes_to_archive(self, family):
        stale = _menu(family, ends_in_days=-1)

        assert archive_expired_menus() == 1

        stale.refresh_from_db()
        assert stale.status == Menu.Status.ARCHIVED

    def test_menu_ending_today_stays_active(self, family):
        """Последний день ещё идёт — меню сегодня нужно."""
        today = _menu(family, ends_in_days=0)

        archive_expired_menus()

        today.refresh_from_db()
        assert today.status == Menu.Status.ACTIVE

    def test_nothing_is_deleted(self, family):
        _menu(family, ends_in_days=-30)
        archive_expired_menus()
        assert Menu.objects.count() == 1

    def test_run_twice_is_a_no_op(self, family):
        _menu(family, ends_in_days=-1)
        assert archive_expired_menus() == 1
        assert archive_expired_menus() == 0

    def test_draft_is_left_alone(self, family):
        """У черновика срока нет — по календарю его не судят."""
        draft = _menu(family, ends_in_days=-5, status=Menu.Status.DRAFT)

        archive_expired_menus()

        draft.refresh_from_db()
        assert draft.status == Menu.Status.DRAFT


class TestTheList:
    def test_expired_is_not_in_the_actual_list(self, client, family):
        fresh = _menu(family, ends_in_days=3)
        _menu(family, ends_in_days=-1)
        client.force_authenticate(family.owner)

        resp = client.get(reverse("menu-list"))

        assert resp.status_code == 200
        assert _ids(resp) == [fresh.id]

    def test_list_does_not_wait_for_the_night_task(self, client, family):
        """Статус ещё active, но день прошёл — в актуальных его быть не должно.

        Ровно этим список и не зависит от того, дожил ли beat до утра.
        """
        stale = _menu(family, ends_in_days=-1)
        assert stale.status == Menu.Status.ACTIVE
        client.force_authenticate(family.owner)

        assert _ids(client.get(reverse("menu-list"))) == []
        assert _ids(client.get(reverse("menu-list"), {"archived": "true"})) == [stale.id]

    def test_archive_holds_both_marked_and_expired(self, client, family):
        marked = _menu(family, ends_in_days=2, status=Menu.Status.ARCHIVED)
        expired = _menu(family, ends_in_days=-2)
        _menu(family, ends_in_days=5)
        client.force_authenticate(family.owner)

        got = set(_ids(client.get(reverse("menu-list"), {"archived": "true"})))

        assert got == {marked.id, expired.id}

    def test_menu_ending_today_is_still_actual(self, client, family):
        today = _menu(family, ends_in_days=0)
        client.force_authenticate(family.owner)

        assert _ids(client.get(reverse("menu-list"))) == [today.id]
        assert _ids(client.get(reverse("menu-list"), {"archived": "true"})) == []

    def test_archived_menu_still_opens_by_id(self, client, family):
        """Архив — не удаление: ссылка на меню продолжает работать."""
        stale = _menu(family, ends_in_days=-1)
        archive_expired_menus()
        client.force_authenticate(family.owner)

        resp = client.get(reverse("menu-detail", args=[stale.id]))

        assert resp.status_code == 200
        assert resp.data["id"] == stale.id

    def test_other_family_sees_nothing(self, client, family, db):
        from apps.users.models import User

        _menu(family, ends_in_days=-1)
        stranger = User.objects.create_user(email="chuzhoy@example.test", name="Чужой", password="pwd12345!")
        other = Family.objects.create(owner=stranger, name="Семья Чужая")
        FamilyMember.objects.create(family=other, user=stranger, role=FamilyMember.Role.HEAD)
        client.force_authenticate(stranger)

        assert _ids(client.get(reverse("menu-list"), {"archived": "true"})) == []
