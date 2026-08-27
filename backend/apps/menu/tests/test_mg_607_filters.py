# /opt/menugen/backend/apps/menu/tests/test_mg_607_filters.py
"""
MG-607: тесты расширенных полей GenerateMenuSerializer и фильтрации.

Покрытие:
  - countries (list) корректно сужает пул рецептов по странам
  - country (single, legacy) продолжает работать
  - countries имеет приоритет над country
  - exclude_allergens (per-request) переопределяет profile.allergies
  - exclude_disliked (per-request) переопределяет profile.disliked_products
"""

# MG_607_V_tests
from __future__ import annotations

from datetime import timedelta as _td
from decimal import Decimal as _D

import pytest
from django.urls import reverse
from django.utils import timezone as _tz
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription as _Sub
from apps.subscriptions.models import SubscriptionPlan as _Plan
from apps.users.models import Profile, User

# ─────────────────────────── helpers ──────────────────────────────────────────


def _attach_premium(family):
    plan, _ = _Plan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": _D("0")},
    )
    if _Sub.objects.filter(family=family, plan=plan).exists():
        return
    _Sub.objects.create(
        family=family,
        plan=plan,
        status=_Sub.Status.ACTIVE,
        started_at=_tz.now() - _td(days=1),
        expires_at=_tz.now() + _td(days=365),
    )


def _mk_recipe(title, country, food_group, ingredients=None, suitable_for=None, **extra):
    return Recipe.objects.create(
        title=title,
        country=country,
        food_group=food_group,
        ingredients=ingredients or [{"name": "neutral", "quantity": "100", "unit": "г"}],
        steps=[{"text": "..."}],
        nutrition={
            "calories": {"value": "300", "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats": {"value": "5", "unit": "г"},
            "carbs": {"value": "30", "unit": "г"},
            "weight": {"value": "200", "unit": "г"},
        },
        categories=[],
        is_published=True,
        suitable_for=suitable_for or ["breakfast", "lunch", "dinner", "snack"],
        **extra,
    )


def _seed_pool_for_country(country):
    """Минимальный пул для одной страны: protein/grain/vegetable/fruit/dairy × 5 шт."""
    for i in range(5):
        _mk_recipe(f"prot-{country}-{i}", country, "protein")
        _mk_recipe(f"grain-{country}-{i}", country, "grain")
        _mk_recipe(f"veg-{country}-{i}", country, "vegetable")
        _mk_recipe(f"fruit-{country}-{i}", country, "fruit")
        _mk_recipe(f"dairy-{country}-{i}", country, "dairy")


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup_family(db):
    """Юзер с allergies=['молоко'], disliked=['лук']; семья с premium; пул по 3 странам."""
    user = User.objects.create_user(
        email="mg607@x.com",
        password="pass1234",
        name="MG607",
        user_type="user",
        allergies=["молоко"],
        disliked_products=["лук"],
    )
    Profile.objects.create(user=user, birth_year=1985, calorie_target=2200)
    family = Family.objects.create(owner=user, name="MG607 Family")
    _attach_premium(family)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)

    for c in ("Россия", "Италия", "Япония"):
        _seed_pool_for_country(c)

    return user, family


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ Countries filter                                                        ║
# ╚═════════════════════════════════════════════════════════════════════════╝


@pytest.mark.django_db
class TestCountriesFilter:
    def test_legacy_country_single_still_works(self, setup_family, client):
        user, _ = setup_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Италия"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        menu = Menu.objects.get(id=resp.data["id"])
        assert menu.filters_used.get("country") == "Италия"

    def test_countries_list_filters_pool(self, setup_family, client):
        user, _ = setup_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "countries": ["Италия", "Япония"]},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        menu = Menu.objects.get(id=resp.data["id"])
        assert menu.filters_used.get("countries") == ["Италия", "Япония"]
        for item in resp.data["items"]:
            assert item["recipe"]["country"] in ("Италия", "Япония"), item

    def test_countries_takes_priority_over_country(self, setup_family, client):
        user, _ = setup_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия", "countries": ["Италия"]},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        for item in resp.data["items"]:
            assert item["recipe"]["country"] == "Италия"


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ exclude_allergens override                                              ║
# ╚═════════════════════════════════════════════════════════════════════════╝


@pytest.mark.django_db
class TestExcludeAllergensOverride:
    def test_default_uses_profile_allergies(self, setup_family, client):
        """Без override — рецепты с 'молоко' исключаются (из profile.allergies)."""
        user, _ = setup_family
        _mk_recipe(
            "milk-soup",
            "Россия",
            "protein",
            ingredients=[{"name": "молоко цельное", "quantity": "1", "unit": "стакан"}],
        )
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        titles = [it["recipe"]["title"] for it in resp.data["items"]]
        assert "milk-soup" not in titles

    def test_override_with_empty_list_disables_allergy_filter(self, setup_family, client):
        """exclude_allergens=[] — полностью выключает фильтр по аллергиям."""
        user, _ = setup_family
        # Весь российский пул — молочный, во всех пищевых группах.
        #
        # Раньше тест удалял белковые рецепты, заводил три молочных и требовал,
        # чтобы хотя бы один попал в меню. Но попадёт ли — решал генератор: на
        # однодневном меню он мог не занять белковую роль вовсе, и в выдаче
        # оставались одни овощи с фруктами. Тест краснел примерно раз из пяти
        # на одной и той же команде, ничего не сообщая про сам фильтр.
        #
        # Молоко во всех группах убирает лотерею: какую бы роль генератор ни
        # занял, российский рецепт будет молочным. А зубы у проверки такие: с
        # работающим фильтром молочные рецепты обходятся стороной, и генератор
        # добирает из Италии с Японией — тогда ни одного «milk-» в меню нет.
        Recipe.objects.filter(country="Россия").delete()
        for group in ("protein", "grain", "vegetable", "fruit", "dairy"):
            for i in range(5):
                _mk_recipe(
                    f"milk-{group}-{i}",
                    "Россия",
                    group,
                    ingredients=[{"name": "молоко цельное", "quantity": "1", "unit": "стакан"}],
                )
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия", "exclude_allergens": []},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        titles = [it["recipe"]["title"] for it in resp.data["items"]]
        assert any(t.startswith("milk-") for t in titles), titles

    def test_override_replaces_profile_allergens(self, setup_family, client):
        """exclude_allergens=['рыба'] — заменяет 'молоко': молочный допущен, рыбный исключён."""
        user, _ = setup_family
        Recipe.objects.filter(country="Россия", food_group="protein").delete()
        for i in range(3):
            _mk_recipe(
                f"milk-{i}",
                "Россия",
                "protein",
                ingredients=[{"name": "молоко цельное", "quantity": "1", "unit": "стакан"}],
            )
            _mk_recipe(
                f"fish-{i}",
                "Россия",
                "protein",
                ingredients=[{"name": "рыба", "quantity": "100", "unit": "г"}],
            )
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия", "exclude_allergens": ["рыба"]},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        titles = [it["recipe"]["title"] for it in resp.data["items"]]
        assert not any(t.startswith("fish-") for t in titles), titles


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ exclude_disliked override                                               ║
# ╚═════════════════════════════════════════════════════════════════════════╝


@pytest.mark.django_db
class TestExcludeDislikedOverride:
    def test_default_uses_profile_disliked(self, setup_family, client):
        """Без override — рецепты с 'лук' (нелюбимое) исключаются."""
        user, _ = setup_family
        _mk_recipe(
            "onion-stew",
            "Россия",
            "vegetable",
            ingredients=[{"name": "лук репчатый", "quantity": "1", "unit": "шт"}],
        )
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        titles = [it["recipe"]["title"] for it in resp.data["items"]]
        assert "onion-stew" not in titles

    def test_override_empty_disables_disliked_filter(self, setup_family, client):
        """exclude_disliked=[] — выключает фильтр disliked."""
        user, _ = setup_family
        # Весь российский пул — луковый, во всех группах. Подробнее о том,
        # почему так, — в комментарии к тесту аллергий выше.
        Recipe.objects.filter(country="Россия").delete()
        for group in ("protein", "grain", "vegetable", "fruit", "dairy"):
            for i in range(5):
                _mk_recipe(
                    f"onion-{group}-{i}",
                    "Россия",
                    group,
                    ingredients=[{"name": "лук репчатый", "quantity": "1", "unit": "шт"}],
                )
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия", "exclude_disliked": []},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        titles = [it["recipe"]["title"] for it in resp.data["items"]]
        assert any(t.startswith("onion-") for t in titles), titles


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ Serializer validation                                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝


@pytest.mark.django_db
class TestSerializerValidation:
    def test_countries_must_be_list_of_strings(self, setup_family, client):
        user, _ = setup_family
        client.force_authenticate(user)
        # пустые строки в массиве — не валидны (allow_blank=False)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "countries": [""]},
            format="json",
        )
        assert resp.status_code == 400

    def test_exclude_allergens_accepts_empty_list(self, setup_family, client):
        """Пустой массив должен валидироваться без ошибки."""
        user, _ = setup_family
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "exclude_allergens": []},
            format="json",
        )
        assert resp.status_code == 201, resp.data
