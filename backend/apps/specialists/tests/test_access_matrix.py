"""MG_SPECACCESS: специалист видит и правит только то, что положено его роли.

До этой правки проверка была одна на всех: «верифицированный специалист с
активным назначением» — и дальше любой мог всё. Тренер правил меню, повару был
открыт коридор калорий клиента.

Здесь закреплены оба слоя правила: роль (таблица в access.py) и живое
назначение — доступ пропадает в тот же момент, когда назначение завершили.
"""

from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.specialists.access import Level, Section, allows, level_for, permissions_for, role_of
from apps.specialists.models import Specialist, SpecialistActionLog, SpecialistAssignment
from apps.users.models import User


def attach_premium(family):
    """MG_SPECINVITE: приглашать специалиста может только премиум-семья."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": Decimal("0")}
    )
    Subscription.objects.get_or_create(
        family=family,
        plan=plan,
        defaults={
            "status": Subscription.Status.ACTIVE,
            "started_at": timezone.now() - timedelta(days=1),
            "expires_at": timezone.now() + timedelta(days=365),
        },
    )


def make_specialist(email, kind, verified=True):
    user = User.objects.create_user(email=email, password="pass12345", name=email.split("@")[0])
    return Specialist.objects.create(user=user, specialist_type=kind, is_verified=verified)


@pytest.fixture
def client_family(db):
    owner = User.objects.create_user(email="client@example.com", password="pass12345", name="Клиент")
    family = Family.objects.create(name="Семья клиента", owner=owner)
    member = FamilyMember.objects.create(family=family, user=owner, role="adult")
    return family, member


@pytest.fixture
def menu_with_item(client_family):
    family, member = client_family
    recipe = Recipe.objects.create(title="Борщ", is_published=True, ingredients=[], nutrition={}, povar_raw={})
    menu = Menu.objects.create(
        family=family,
        creator_id=member.user_id,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 1),
        period_days=1,
    )
    item = MenuItem.objects.create(
        menu=menu, member=member, day_offset=0, meal_type="lunch", meal_slot="lunch", recipe=recipe
    )
    return menu, item


def assign(specialist, family, status=SpecialistAssignment.Status.ACTIVE):
    return SpecialistAssignment.objects.create(
        family=family,
        specialist=specialist,
        specialist_type=specialist.specialist_type,
        status=status,
    )


def api_for(specialist):
    c = APIClient()
    c.force_authenticate(specialist.user)
    return c


# ── таблица как таковая ──────────────────────────────────────────────────────


class TestMatrix:
    def test_каждая_роль_знает_свои_разделы(self):
        assert level_for("dietitian", Section.MENU) == Level.WRITE
        assert level_for("trainer", Section.MENU) == Level.READ
        assert level_for("cook", Section.SHOPPING) == Level.WRITE

    def test_дневник_повару_не_положен(self):
        """Дневник питания — личное; повару он для работы не нужен."""
        assert level_for("cook", Section.DIARY) == Level.NONE

    def test_коридор_калорий_повар_только_читает(self):
        assert level_for("cook", Section.PROFILE) == Level.READ

    def test_неизвестная_роль_не_получает_ничего(self):
        """Забыть открыть безопаснее, чем забыть закрыть."""
        for section in Section:
            assert level_for("massagist", section) == Level.NONE

    def test_правка_подразумевает_чтение(self):
        class _A:
            specialist_type = "cook"
            specialist = None

        assert allows(_A(), Section.FRIDGE, write=True)
        assert allows(_A(), Section.FRIDGE, write=False)

    def test_чтение_не_даёт_правки(self):
        class _A:
            specialist_type = "trainer"
            specialist = None

        assert allows(_A(), Section.MENU, write=False)
        assert not allows(_A(), Section.MENU, write=True)

    def test_без_назначения_нет_ничего(self):
        assert not allows(None, Section.MENU)

    def test_права_для_интерфейса_перечисляют_все_разделы(self):
        perms = permissions_for("dietitian")

        assert set(perms) == {s.value for s in Section}
        assert perms[Section.SHOPPING] == Level.NONE


@pytest.mark.django_db
class TestRoleSource:
    def test_роль_берётся_из_назначения(self, client_family):
        """Позвали поваром — права поварские, даже если в профиле иное."""
        family, _ = client_family
        spec = make_specialist("both@example.com", Specialist.Type.DIETITIAN)
        assignment = SpecialistAssignment.objects.create(
            family=family, specialist=spec, specialist_type="cook", status=SpecialistAssignment.Status.ACTIVE
        )

        assert role_of(assignment) == "cook"

    def test_у_старых_назначений_роль_из_профиля(self, client_family):
        """В назначениях, созданных до этой правки, поле пустое."""
        family, _ = client_family
        spec = make_specialist("old@example.com", Specialist.Type.TRAINER)
        assignment = SpecialistAssignment.objects.create(
            family=family, specialist=spec, specialist_type="", status=SpecialistAssignment.Status.ACTIVE
        )

        assert role_of(assignment) == "trainer"


# ── правило в бою: эндпоинты кабинета ────────────────────────────────────────


@pytest.mark.django_db
class TestMenuAccess:
    def swap_url(self, family, menu, item):
        return reverse("cabinet-menu-item-swap", args=[family.id, menu.id, item.id])

    def test_диетолог_меняет_блюдо(self, client_family, menu_with_item):
        family, _ = client_family
        menu, item = menu_with_item
        spec = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(spec, family)
        other = Recipe.objects.create(title="Суп", is_published=True, ingredients=[], nutrition={}, povar_raw={})

        r = api_for(spec).patch(self.swap_url(family, menu, item), {"recipe_id": other.id}, format="json")

        assert r.status_code == 200, r.data
        item.refresh_from_db()
        assert item.recipe_id == other.id

    def test_тренер_меню_читает_но_не_правит(self, client_family, menu_with_item):
        family, _ = client_family
        menu, item = menu_with_item
        spec = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(spec, family)
        other = Recipe.objects.create(title="Суп", is_published=True, ingredients=[], nutrition={}, povar_raw={})
        api = api_for(spec)

        assert api.get(reverse("cabinet-client-menus", args=[family.id])).status_code == 200

        r = api.patch(self.swap_url(family, menu, item), {"recipe_id": other.id}, format="json")

        assert r.status_code == 403
        item.refresh_from_db()
        assert item.recipe_id != other.id

    def test_повар_меняет_блюдо(self, client_family, menu_with_item):
        family, _ = client_family
        menu, item = menu_with_item
        spec = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(spec, family)
        other = Recipe.objects.create(title="Суп", is_published=True, ingredients=[], nutrition={}, povar_raw={})

        r = api_for(spec).patch(self.swap_url(family, menu, item), {"recipe_id": other.id}, format="json")

        assert r.status_code == 200, r.data


@pytest.mark.django_db
class TestRecommendationAccess:
    def url(self, family):
        return reverse("cabinet-recommendations", args=[family.id])

    def test_диетолог_пишет_рекомендацию(self, client_family):
        family, member = client_family
        spec = make_specialist("diet2@example.com", Specialist.Type.DIETITIAN)
        assign(spec, family)

        r = api_for(spec).post(
            self.url(family), {"rec_type": "supplement", "name": "Витамин D", "member": member.id}, format="json"
        )

        assert r.status_code == 201, r.data

    def test_повар_рекомендаций_не_пишет(self, client_family):
        """У повара профиль клиента только на чтение."""
        family, member = client_family
        spec = make_specialist("cook2@example.com", Specialist.Type.COOK)
        assign(spec, family)
        api = api_for(spec)

        assert api.get(self.url(family)).status_code == 200

        r = api.post(self.url(family), {"rec_type": "food", "name": "Меньше соли"}, format="json")

        assert r.status_code == 403


@pytest.mark.django_db
class TestAssignmentGate:
    def test_чужая_семья_не_видна(self, client_family):
        """Отказ — 404: подтверждать существование чужой семьи незачем."""
        family, _ = client_family
        spec = make_specialist("stranger@example.com", Specialist.Type.DIETITIAN)

        r = api_for(spec).get(reverse("cabinet-client-menus", args=[family.id]))

        assert r.status_code in (403, 404)

    def test_завершённое_назначение_закрывает_доступ(self, client_family):
        family, _ = client_family
        spec = make_specialist("ended@example.com", Specialist.Type.DIETITIAN)
        assignment = assign(spec, family)
        api = api_for(spec)
        assert api.get(reverse("cabinet-client-menus", args=[family.id])).status_code == 200

        assignment.status = SpecialistAssignment.Status.ENDED
        assignment.save(update_fields=["status"])

        assert api.get(reverse("cabinet-client-menus", args=[family.id])).status_code in (403, 404)

    def test_неверифицированный_специалист_не_работает(self, client_family):
        family, _ = client_family
        spec = make_specialist("new@example.com", Specialist.Type.DIETITIAN, verified=False)
        assign(spec, family)

        r = api_for(spec).get(reverse("cabinet-client-menus", args=[family.id]))

        assert r.status_code in (403, 404)


@pytest.mark.django_db
class TestInviteRole:
    def test_роль_назначения_равна_роли_специалиста(self, client_family):
        """Иначе приглашающий сам решал бы, какие права выдать."""
        family, member = client_family
        spec = make_specialist("diet3@example.com", Specialist.Type.DIETITIAN)
        api = APIClient()
        api.force_authenticate(member.user)

        r = api.post(
            reverse("specialist-invite"),
            {"email": "diet3@example.com", "specialist_type": "cook"},
            format="json",
        )

        assert r.status_code == 400
        assert "зарегистрирован" in r.data["detail"]
        assert not SpecialistAssignment.objects.filter(family=family).exists()

    def test_приглашение_без_указания_роли_берёт_её_из_профиля(self, client_family):
        family, member = client_family
        attach_premium(family)
        make_specialist("cook3@example.com", Specialist.Type.COOK)
        api = APIClient()
        api.force_authenticate(member.user)

        r = api.post(reverse("specialist-invite"), {"email": "cook3@example.com"}, format="json")

        assert r.status_code == 201, r.data
        assert SpecialistAssignment.objects.get(family=family).specialist_type == "cook"


@pytest.mark.django_db
class TestJournal:
    def test_замена_блюда_попадает_в_журнал(self, client_family, menu_with_item):
        family, _ = client_family
        menu, item = menu_with_item
        spec = make_specialist("diet4@example.com", Specialist.Type.DIETITIAN)
        assign(spec, family)
        other = Recipe.objects.create(title="Суп", is_published=True, ingredients=[], nutrition={}, povar_raw={})

        api_for(spec).patch(
            reverse("cabinet-menu-item-swap", args=[family.id, menu.id, item.id]),
            {"recipe_id": other.id},
            format="json",
        )

        entry = SpecialistActionLog.objects.get(family=family)
        assert (entry.section, entry.action) == (Section.MENU, "swap_item")
        assert "Борщ" in entry.summary and "Суп" in entry.summary

    def test_чтение_журнал_не_засоряет(self, client_family):
        family, _ = client_family
        spec = make_specialist("diet5@example.com", Specialist.Type.DIETITIAN)
        assign(spec, family)

        api_for(spec).get(reverse("cabinet-client-menus", args=[family.id]))

        assert not SpecialistActionLog.objects.exists()

    def test_рекомендация_попадает_в_журнал(self, client_family):
        family, member = client_family
        spec = make_specialist("diet6@example.com", Specialist.Type.DIETITIAN)
        assign(spec, family)

        api_for(spec).post(
            reverse("cabinet-recommendations", args=[family.id]),
            {"rec_type": "supplement", "name": "Магний", "member": member.id},
            format="json",
        )

        entry = SpecialistActionLog.objects.get(family=family)
        assert entry.action == "add_recommendation"
        assert entry.summary == "Магний"


@pytest.mark.django_db
class TestProfileEndpoint:
    def test_профиль_отдаёт_права_роли(self):
        spec = make_specialist("cook4@example.com", Specialist.Type.COOK)

        r = api_for(spec).get(reverse("specialist-profile"))

        assert r.status_code == 200
        assert r.data["permissions"][Section.SHOPPING] == Level.WRITE
        assert r.data["permissions"][Section.DIARY] == Level.NONE
