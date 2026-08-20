"""MG_DIETITIAN: разбор рациона и проверка исключений.

Нутрициологу нужен состав тарелки, а не калораж. Считается по полям рецепта,
которые уже проставлены: группа продукта, тип белка, жирная рыба, красное мясо,
аллергены.

Отдельно проверяется честность ответа: доля записей «своей едой» (у них состава
нет) и покрытие по клетчатке (она заполнена не у всех рецептов). Без этих двух
чисел разбор выглядит точным, не будучи таким.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.specialists.models import Specialist, SpecialistAssignment
from apps.users.models import User


@pytest.fixture
def client_family(db):
    user = User.objects.create_user(email="client@example.com", name="Клиент", password="pass12345")
    family = Family.objects.create(owner=user, name="Семья клиента")
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return family, user, member


def make_specialist(email, spec_type):
    user = User.objects.create_user(email=email, name=email.split("@")[0], password="pass12345")
    prof = Specialist.objects.create(user=user, specialist_type=spec_type, is_verified=True)
    return user, prof


def assign(prof, family):
    return SpecialistAssignment.objects.create(
        family=family, specialist=prof, specialist_type=prof.specialist_type, status=SpecialistAssignment.Status.ACTIVE
    )


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def recipe(title, **kwargs):
    return Recipe.objects.create(title=title, is_published=True, **kwargs)


def eat(member, day, recipe_obj=None, custom="Своя еда"):
    return DiaryEntry.objects.create(
        member=member,
        date=day,
        meal_type=DiaryEntry.MealType.LUNCH,
        recipe=recipe_obj,
        custom_name="" if recipe_obj else custom,
        nutrition={},
        is_eaten=True,
    )


@pytest.mark.django_db
class TestRation:
    def test_состав_по_группам(self, client_family):
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        eat(member, today, recipe("Салат", food_group=Recipe.FoodGroup.VEGETABLE))
        eat(member, today, recipe("Каша", food_group=Recipe.FoodGroup.GRAIN))
        eat(member, today - timedelta(days=1), recipe("Овощи гриль", food_group=Recipe.FoodGroup.VEGETABLE))

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        assert r.status_code == 200, r.data
        me = r.data["members"][0]
        groups = {g["group"]: g for g in me["food_groups"]}
        assert groups["vegetable"]["count"] == 2
        assert groups["vegetable"]["percent"] == pytest.approx(66.7, abs=0.1)

    def test_доля_записей_без_рецепта_видна(self, client_family):
        """«Овощей 12%» при половине записей вручную — это не факт."""
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        eat(member, today, recipe("Салат", food_group=Recipe.FoodGroup.VEGETABLE))
        eat(member, today, None)
        eat(member, today, None)

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        cov = r.data["members"][0]["coverage"]
        assert cov["with_recipe"] == 1
        assert cov["manual"] == 2
        assert cov["percent"] == pytest.approx(33.3, abs=0.1)

    def test_источники_белка(self, client_family):
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        eat(member, today, recipe("Курица", protein_type=Recipe.ProteinType.ANIMAL))
        eat(member, today, recipe("Чечевица", protein_type=Recipe.ProteinType.PLANT))
        eat(member, today, recipe("Индейка", protein_type=Recipe.ProteinType.ANIMAL))

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        sources = {s["type"]: s["count"] for s in r.data["members"][0]["protein_sources"]}
        assert sources == {"animal": 2, "plant": 1}

    def test_рыба_и_красное_мясо_считаются_днями(self, client_family):
        """Два куска лосося за обед — это один день с рыбой, а не два."""
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        salmon = recipe("Лосось", is_fatty_fish=True)
        eat(member, today, salmon)
        eat(member, today, salmon)
        eat(member, today, recipe("Говядина", is_red_meat=True))

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        me = r.data["members"][0]
        assert me["fatty_fish_days"] == 1
        assert me["red_meat_days"] == 1

    def test_разнообразие_и_повторы(self, client_family):
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        oatmeal = recipe("Овсянка")
        for i in range(4):
            eat(member, today - timedelta(days=i), oatmeal)
        eat(member, today, recipe("Салат"))

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        variety = r.data["members"][0]["variety"]
        assert variety["distinct_dishes"] == 2
        assert variety["top_repeats"][0] == {"title": "Овсянка", "count": 4}

    def test_клетчатка_с_покрытием(self, client_family):
        """Сумма без покрытия выглядит фактом, будучи заниженной."""
        family, _, member = client_family
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        eat(member, today, recipe("С клетчаткой", nutrition={"fiber": 6}))
        eat(member, today, recipe("Со словарём", nutrition={"fiber": {"value": 4}}))
        eat(member, today, recipe("Без данных", nutrition={}))

        r = api(diet_user).get(reverse("cabinet-client-ration", args=[family.id]))

        fiber = r.data["members"][0]["fiber"]
        assert fiber["total_g"] == 10.0
        assert fiber["entries_counted"] == 2
        assert fiber["coverage_percent"] == pytest.approx(66.7, abs=0.1)

    def test_повару_разбор_закрыт(self, client_family):
        family, _, _ = client_family
        cook_user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(prof, family)

        r = api(cook_user).get(reverse("cabinet-client-ration", args=[family.id]))

        assert r.status_code == 403


@pytest.mark.django_db
class TestExclusions:
    def test_аллерген_в_дневнике_находится(self, client_family):
        family, user, member = client_family
        user.allergies = ["milk"]
        user.save(update_fields=["allergies"])
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        eat(member, timezone.localdate(), recipe("Сырники", allergens=["milk"]))

        r = api(diet_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        assert r.status_code == 200, r.data
        hits = r.data["members"][0]["diary"]
        assert hits[0]["title"] == "Сырники"
        assert "Молоко" in hits[0]["reasons"][0]

    def test_аллерген_в_активном_меню_находится(self, client_family):
        """Меню могли собрать до того, как аллерген появился в профиле."""
        family, user, member = client_family
        user.allergies = ["milk"]
        user.save(update_fields=["allergies"])
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        today = timezone.localdate()
        menu = Menu.objects.create(
            family=family,
            creator_id=user.id,
            period_days=1,
            start_date=today,
            end_date=today,
            status=Menu.Status.ACTIVE,
        )
        MenuItem.objects.create(
            menu=menu,
            recipe=recipe("Молочный суп", allergens=["milk"]),
            meal_type=MenuItem.MealType.LUNCH,
            day_offset=0,
        )

        r = api(diet_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        assert [h["title"] for h in r.data["members"][0]["menu"]] == ["Молочный суп"]

    def test_нелюбимое_ловится_по_названию(self, client_family):
        family, user, member = client_family
        user.disliked_products = ["кинза"]
        user.save(update_fields=["disliked_products"])
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        eat(member, timezone.localdate(), recipe("Салат с кинзой"))

        r = api(diet_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        assert "нелюбимое: кинза" in r.data["members"][0]["diary"][0]["reasons"]

    def test_чистый_рацион_даёт_пустой_список(self, client_family):
        family, user, member = client_family
        user.allergies = ["milk"]
        user.save(update_fields=["allergies"])
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        eat(member, timezone.localdate(), recipe("Гречка", allergens=[]))

        r = api(diet_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        me = r.data["members"][0]
        assert me["diary"] == []
        assert me["menu"] == []
        assert me["watching"]["allergens"] == ["Молоко"]

    def test_своя_запись_проверяется_по_названию(self, client_family):
        """Запись без рецепта — тоже еда, и исключение в ней надо увидеть."""
        family, user, member = client_family
        user.disliked_products = ["грибы"]
        user.save(update_fields=["disliked_products"])
        diet_user, prof = make_specialist("diet@example.com", Specialist.Type.DIETITIAN)
        assign(prof, family)
        eat(member, timezone.localdate(), None, custom="Жареные грибы")

        r = api(diet_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        assert r.data["members"][0]["diary"][0]["title"] == "Жареные грибы"

    def test_тренер_проверку_видит(self, client_family):
        """У тренера профиль на запись — ограничения клиента ему доступны."""
        family, _, _ = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)

        r = api(trainer_user).get(reverse("cabinet-client-exclusions", args=[family.id]))

        assert r.status_code == 200
