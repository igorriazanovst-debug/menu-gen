"""MG_MENUAPPLY: составленное меню доходит до клиента.

Конструктор строил `ConstructedMenu`, а эндпоинты конструктора отдают только
меню с `author=request.user` — клиент составленного не видел никак, специалист
работал в пустоту.

Теперь меню разворачивается в обычное `Menu` семьи: на нём держится всё
остальное — дневник с планом-фактом, список покупок, мобильное приложение, и
второй тип меню на клиентской стороне заводить не пришлось.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import ConstructedMeal, ConstructedMealItem, ConstructedMenu, Menu
from apps.recipes.models import Recipe
from apps.specialists.models import Specialist, SpecialistAssignment
from apps.users.models import User


@pytest.fixture
def recipes(db):
    return [
        Recipe.objects.create(title=f"Блюдо {i}", is_published=True)
        for i in range(4)
    ]


def make_client_family(tag="client"):
    user = User.objects.create_user(email=f"{tag}@example.com", name=tag, password="pass12345")
    family = Family.objects.create(owner=user, name=f"Семья {tag}")
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return family, user


def make_specialist(email, spec_type):
    user = User.objects.create_user(email=email, name=email.split("@")[0], password="pass12345")
    prof = Specialist.objects.create(user=user, specialist_type=spec_type, is_verified=True)
    return user, prof


def assign(prof, family, spec_type=None):
    return SpecialistAssignment.objects.create(
        family=family,
        specialist=prof,
        specialist_type=spec_type or prof.specialist_type,
        status=SpecialistAssignment.Status.ACTIVE,
    )


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def build_menu(author, family, recipes, meal_names=("Завтрак", "Обед", "Ужин"), days=1):
    menu = ConstructedMenu.objects.create(name="Неделя", author=author, client_family=family, days=days)
    for day in range(days):
        for order, name in enumerate(meal_names):
            meal = ConstructedMeal.objects.create(menu=menu, day_index=day, order=order, name=name)
            ConstructedMealItem.objects.create(meal=meal, recipe=recipes[order % len(recipes)], quantity=1)
    return menu


@pytest.mark.django_db
class TestApply:
    def test_меню_появляется_у_клиента(self, recipes):
        family, client_user = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]), {"start_date": "2026-09-01"}, format="json"
        )

        assert r.status_code == 201, r.data
        menu = Menu.objects.get(id=r.data["menu_id"])
        assert menu.family_id == family.id
        assert menu.status == Menu.Status.ACTIVE
        assert menu.modified_by == Menu.ModifiedBy.SPECIALIST
        assert menu.items.count() == 3

    def test_приёмы_раскладываются_по_слотам(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        menu = Menu.objects.get(id=r.data["menu_id"])
        assert sorted(menu.items.values_list("meal_slot", flat=True)) == ["breakfast", "dinner", "lunch"]

    def test_перекусы_нумеруются(self, recipes):
        """Мобильное различает слоты по именам: два «snack» слиплись бы в один."""
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(
            spec_user, family, recipes, meal_names=("Завтрак", "Перекус", "Обед", "Полдник", "Ужин")
        )

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        slots = set(Menu.objects.get(id=r.data["menu_id"]).items.values_list("meal_slot", flat=True))
        assert {"snack1", "snack2"} <= slots

    def test_пятиразовое_меню_помечено_в_фильтрах(self, recipes):
        """Мобильное решает по filters_used, показывать ли строки перекусов."""
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(
            spec_user, family, recipes, meal_names=("Завтрак", "Перекус", "Обед", "Полдник", "Ужин")
        )

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert Menu.objects.get(id=r.data["menu_id"]).filters_used["meal_plan_type"] == "5"

    def test_трёхразовое_меню_помечено_как_три(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert Menu.objects.get(id=r.data["menu_id"]).filters_used["meal_plan_type"] == "3"

    def test_дни_сохраняют_порядок(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes, days=3)

        r = api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]), {"start_date": "2026-09-01"}, format="json"
        )

        menu = Menu.objects.get(id=r.data["menu_id"])
        assert menu.period_days == 3
        assert menu.start_date == date(2026, 9, 1)
        assert menu.end_date == date(2026, 9, 3)
        assert sorted(set(menu.items.values_list("day_offset", flat=True))) == [0, 1, 2]

    def test_без_даты_начинается_сегодня(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert Menu.objects.get(id=r.data["menu_id"]).start_date == date.today()

    def test_меню_помечается_выданным(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        constructed.refresh_from_db()
        assert constructed.status == ConstructedMenu.Status.PUBLISHED
        assert constructed.applied_menu_id == r.data["menu_id"]

    def test_клиент_видит_выданное_меню_в_своём_списке(self, recipes):
        """Ради этого всё и делалось: меню доходит обычным клиентским путём."""
        family, client_user = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)
        api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]),
            {"start_date": str(date.today())},
            format="json",
        )

        r = api(client_user).get("/api/v1/menu/")

        assert r.status_code == 200, r.data
        constructed.refresh_from_db()
        rows = r.data["results"] if isinstance(r.data, dict) and "results" in r.data else r.data
        assert [m["id"] for m in rows] == [constructed.applied_menu_id]


@pytest.mark.django_db
class TestApplyAccess:
    def test_тренер_выдать_меню_не_может(self, recipes):
        """Меню тренеру открыто на чтение — класть его клиенту он не вправе."""
        family, _ = make_client_family()
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        constructed = build_menu(trainer_user, family, recipes)

        r = api(trainer_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert r.status_code == 403
        assert not Menu.objects.filter(family=family).exists()

    def test_повар_выдать_может(self, recipes):
        family, _ = make_client_family()
        cook_user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(prof, family)
        constructed = build_menu(cook_user, family, recipes)

        r = api(cook_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert r.status_code == 201, r.data

    def test_после_завершения_назначения_выдать_нельзя(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assignment = assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)
        assignment.status = SpecialistAssignment.Status.ENDED
        assignment.save(update_fields=["status"])

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert r.status_code == 403
        assert not Menu.objects.filter(family=family).exists()

    def test_чужое_меню_выдать_нельзя(self, recipes):
        family, _ = make_client_family()
        author_user, author_prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(author_prof, family)
        constructed = build_menu(author_user, family, recipes)
        other_user, other_prof = make_specialist("other@example.com", Specialist.Type.DIETITIAN)
        assign(other_prof, family)

        r = api(other_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert r.status_code == 404

    def test_шаблон_без_клиента_выдать_нельзя(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = ConstructedMenu.objects.create(name="Шаблон", author=spec_user, days=1)

        r = api(spec_user).post(reverse("constructor-apply", args=[constructed.id]), {}, format="json")

        assert r.status_code == 400

    def test_кривая_дата_отклоняется(self, recipes):
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)

        r = api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]), {"start_date": "не дата"}, format="json"
        )

        assert r.status_code == 400
        assert not Menu.objects.filter(family=family).exists()


@pytest.mark.django_db
class TestSlotResolution:
    """Раскладка приёмов — чистая функция, проверяем без HTTP."""

    def test_безымянные_приёмы_идут_по_порядку(self):
        from apps.menu.constructor_apply import resolve_slots

        class M:
            def __init__(self, name):
                self.name = name

        meals = [M(""), M(""), M(""), M("")]

        slots = resolve_slots(meals)

        assert [s[0] for s in slots] == ["breakfast", "lunch", "dinner", "snack1"]

    def test_названия_важнее_порядка(self):
        from apps.menu.constructor_apply import resolve_slots

        class M:
            def __init__(self, name):
                self.name = name

        meals = [M("Ужин"), M("Завтрак")]

        slots = resolve_slots(meals)

        assert [s[0] for s in slots] == ["dinner", "breakfast"]


@pytest.mark.django_db
class TestReapply:
    def test_повторная_выдача_создаёт_новое_меню(self, recipes):
        """Меню на другую неделю — новое меню, а не правка прежнего."""
        family, _ = make_client_family()
        spec_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        constructed = build_menu(spec_user, family, recipes)
        first = api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]), {"start_date": str(date.today())}, format="json"
        )

        second = api(spec_user).post(
            reverse("constructor-apply", args=[constructed.id]),
            {"start_date": str(date.today() + timedelta(days=7))},
            format="json",
        )

        assert first.data["menu_id"] != second.data["menu_id"]
        assert Menu.objects.filter(family=family).count() == 2
        constructed.refresh_from_db()
        assert constructed.applied_menu_id == second.data["menu_id"]
