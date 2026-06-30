"""MG-605.D — POST /api/v1/diary/import-from-menu/?menu_id=&date=

Покрывает:
- успешный импорт (создаёт DiaryEntry для каждого MenuItem)
- идемпотентность (повторный вызов — skipped, не дубли)
- isolation: импортируются только items target-члена + общие (member IS NULL)
- HEAD импортирует за члена семьи через ?member_id=
- MEMBER не может импортировать за другого (403)
- меню чужой семьи → 404
- меню не существует → 404
- freemium: free-юзер тоже может импортировать (200)
- DIARY_MULTIDAY: дни меню разносятся по датам = старт + day_offset
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────


def _user(email):
    return User.objects.create_user(email=email, password="pwd12345!", name=email.split("@")[0])


def _premium_family(owner, members=()):
    fam = Family.objects.create(owner=owner)
    head = FamilyMember.objects.create(family=fam, user=owner, role=FamilyMember.Role.HEAD)
    extra = []
    for u in members:
        extra.append(FamilyMember.objects.create(family=fam, user=u, role=FamilyMember.Role.MEMBER))
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=30),
    )
    return fam, head, extra


def _recipe(title="Овсянка", kcal=300):
    return Recipe.objects.create(
        title=title,
        ingredients=[],
        steps=[],
        nutrition={
            "calories": {"value": str(kcal), "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats": {"value": "5", "unit": "г"},
            "carbs": {"value": "50", "unit": "г"},
        },
        is_published=True,
    )


def _menu(family, start=None):
    start = start or date.today()
    return Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        period_days=1,
        start_date=start,
        end_date=start,
        status=Menu.Status.ACTIVE,
    )


def _menu_item(menu, recipe, member=None, day_offset=0, meal_type="breakfast", meal_slot="breakfast", qty=1):
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        member=member,
        day_offset=day_offset,
        meal_type=meal_type,
        meal_slot=meal_slot,
        component_role="other",
        quantity=Decimal(str(qty)),
    )


@pytest.fixture
def client():
    return APIClient()


# ─── tests ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDiaryImportFromMenu:

    def test_import_creates_planned_entries(self, client):
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = _menu(fam)
        mi = _menu_item(menu, r, member=head)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            data=None,
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 200, resp.data
        assert resp.data["created"] == 1
        assert resp.data["skipped"] == 0
        assert len(resp.data["entries"]) == 1

        entry = DiaryEntry.objects.get(planned_menu_item=mi)
        assert entry.member_id == head.id
        assert entry.date == date.today()
        assert entry.meal_type == "breakfast"
        assert entry.is_eaten is False
        assert entry.recipe_id == r.id

    def test_import_spreads_days_by_offset(self, client):
        """DIARY_MULTIDAY: дни меню разносятся по реальным датам = старт + day_offset."""
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = Menu.objects.create(
            family=fam,
            creator_id=fam.owner_id,
            period_days=3,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status=Menu.Status.ACTIVE,
        )
        mi0 = _menu_item(menu, r, member=head, day_offset=0, meal_type="breakfast", meal_slot="breakfast")
        mi1 = _menu_item(menu, r, member=head, day_offset=1, meal_type="lunch", meal_slot="lunch")
        mi2 = _menu_item(menu, r, member=head, day_offset=2, meal_type="dinner", meal_slot="dinner")

        start = date.today() + timedelta(days=1)  # старт в будущем (сценарий «поход»)
        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={start}",
        )
        assert resp.status_code == 200, resp.data
        assert resp.data["created"] == 3
        assert DiaryEntry.objects.get(planned_menu_item=mi0).date == start
        assert DiaryEntry.objects.get(planned_menu_item=mi1).date == start + timedelta(days=1)
        assert DiaryEntry.objects.get(planned_menu_item=mi2).date == start + timedelta(days=2)

    def test_range_filter_returns_multiple_days(self, client):
        """DIARY_MULTIDAY: GET /diary/?from=&to= отдаёт записи всех дат диапазона."""
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = Menu.objects.create(
            family=fam,
            creator_id=fam.owner_id,
            period_days=2,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=Menu.Status.ACTIVE,
        )
        _menu_item(menu, r, member=head, day_offset=0, meal_type="breakfast", meal_slot="breakfast")
        _menu_item(menu, r, member=head, day_offset=1, meal_type="lunch", meal_slot="lunch")
        client.force_authenticate(head_user)
        client.post(reverse("diary-import-from-menu"), QUERY_STRING=f"menu_id={menu.id}&date={date.today()}")

        d0 = date.today()
        d1 = date.today() + timedelta(days=1)
        resp = client.get(reverse("diary-list"), {"from": str(d0), "to": str(d1), "page_size": 1000})
        assert resp.status_code == 200
        dates = sorted({e["date"] for e in resp.data["results"]})
        assert dates == [str(d0), str(d1)]

    def test_import_idempotent(self, client):
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r, member=head)

        client.force_authenticate(head_user)
        qs = f"menu_id={menu.id}&date={date.today()}"
        # 1-й вызов
        r1 = client.post(reverse("diary-import-from-menu"), QUERY_STRING=qs)
        # 2-й вызов
        r2 = client.post(reverse("diary-import-from-menu"), QUERY_STRING=qs)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.data["created"] == 1
        assert r2.data["created"] == 0
        assert r2.data["skipped"] == 1
        assert DiaryEntry.objects.count() == 1

    def test_import_only_target_members_items(self, client):
        """Импорт за HEAD — берёт MenuItem'ы HEAD + общие (member IS NULL),
        но НЕ берёт items другого члена семьи."""
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        mi_head = _menu_item(menu, r, member=head, meal_slot="breakfast", meal_type="breakfast")
        mi_common = _menu_item(menu, r, member=None, meal_slot="lunch", meal_type="lunch", day_offset=0)
        _menu_item(menu, r, member=other, meal_slot="dinner", meal_type="dinner", day_offset=0)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 200
        assert resp.data["created"] == 2  # head + common
        entries_for_head = DiaryEntry.objects.filter(member=head)
        assert entries_for_head.count() == 2
        planned_ids = set(entries_for_head.values_list("planned_menu_item_id", flat=True))
        assert planned_ids == {mi_head.id, mi_common.id}

    def test_head_imports_for_member(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        mi = _menu_item(menu, r, member=other)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}&member_id={other.id}",
        )
        assert resp.status_code == 200
        assert resp.data["created"] == 1
        entry = DiaryEntry.objects.get(planned_menu_item=mi)
        assert entry.member_id == other.id

    def test_member_cannot_import_for_other(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r, member=head)

        client.force_authenticate(other_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}&member_id={head.id}",
        )
        assert resp.status_code == 403

    def test_menu_from_other_family_404(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam1, head1, _ = _premium_family(head_user)
        fam2 = Family.objects.create(owner=other_user)
        FamilyMember.objects.create(family=fam2, user=other_user, role=FamilyMember.Role.HEAD)
        r = _recipe()
        foreign_menu = _menu(fam2)
        _menu_item(foreign_menu, r)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={foreign_menu.id}&date={date.today()}",
        )
        assert resp.status_code == 404

    def test_menu_not_found(self, client):
        head_user = _user("head@example.com")
        _premium_family(head_user)
        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id=999999&date={date.today()}",
        )
        assert resp.status_code == 404

    def test_free_user_can_import(self, client):
        # freemium: дневник (вкл. импорт из меню) открыт free-юзерам — больше не 403.
        user = _user("nopremium@example.com")
        fam = Family.objects.create(owner=user)
        FamilyMember.objects.create(family=fam, user=user, role=FamilyMember.Role.HEAD)
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r)

        client.force_authenticate(user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 200, resp.data
        assert resp.data["created"] == 1

    def test_invalid_query_params(self, client):
        head_user = _user("head@example.com")
        _premium_family(head_user)
        client.force_authenticate(head_user)
        # без menu_id
        resp = client.post(reverse("diary-import-from-menu"), QUERY_STRING=f"date={date.today()}")
        assert resp.status_code == 400
        # без date
        resp = client.post(reverse("diary-import-from-menu"), QUERY_STRING="menu_id=1")
        assert resp.status_code == 400
