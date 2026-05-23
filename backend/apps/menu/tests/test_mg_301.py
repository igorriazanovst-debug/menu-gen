"""
MG-301: тесты метода тарелки.
- основной приём = grain + protein + vegetable (3 компонента)
- перекус = 1 компонент
- сохраняется component_role в БД
- при пустом пуле роли API возвращает 400 + читаемое сообщение
- AuditLog содержит запись "menu.generate.empty_role_pool"
"""

# MG_301_V_tests
import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import MenuItem
from apps.recipes.models import Recipe
from apps.sync.models import AuditLog
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


def _mk_recipe(title, food_group, suitable_for=None, dish_type="main", **extra):
    return Recipe.objects.create(
        title=title,
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "Шаг 1"}],
        nutrition={"calories": {"value": "300", "unit": "ккал"}},
        categories=[],
        is_published=True,
        food_group=food_group,
        dish_type=dish_type,
        suitable_for=suitable_for or ["breakfast", "lunch", "dinner", "snack"],
        **extra,
    )


@pytest.fixture
def setup_full(db):
    """Все 4 роли есть: protein/grain/vegetable/fruit/dairy."""
    user = User.objects.create_user(email="mg301@example.com", name="Тестер301", password="pass1234")
    family = Family.objects.create(owner=user, name="Семья 301")
    _attach_premium(family)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    for i in range(5):
        _mk_recipe(f"Завтрак {i}", "grain", dish_type="breakfast_dish")
        _mk_recipe(f"Суп {i}", "vegetable", dish_type="soup")
        _mk_recipe(f"Горячее {i}", "protein", dish_type="main")
        _mk_recipe(f"Салат {i}", "vegetable", dish_type="salad")
        _mk_recipe(f"Перекус {i}", "fruit", dish_type="snack")
        _mk_recipe(f"Напиток {i}", "fruit", dish_type="drink")
        _mk_recipe(f"Десерт {i}", "grain", dish_type="dessert")
        _mk_recipe(f"Выпечка {i}", "grain", dish_type="bakery")
    return user, family, member


@pytest.mark.django_db
class TestPlateMethodComponents:
    def test_main_meal_has_three_components(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        items = resp.data["items"]
        # RB001_V_step4: lunch=soup+main+salad+dessert+bakery, dinner=main+salad
        lunch_items = [i for i in items if i["meal_slot"] == "lunch"]
        roles = {i["component_role"] for i in lunch_items}
        assert "main" in roles, f"lunch roles: {roles}"
        assert roles <= {"soup", "main", "salad", "dessert", "bakery"}, f"lunch roles: {roles}"
        dinner_items = [i for i in items if i["meal_slot"] == "dinner"]
        roles = {i["component_role"] for i in dinner_items}
        assert "main" in roles, f"dinner roles: {roles}"
        assert roles <= {"main", "salad"}, f"dinner roles: {roles}"

    def test_breakfast_has_three_components(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201
        breakfast = [i for i in resp.data["items"] if i["meal_slot"] == "breakfast"]
        roles = {i["component_role"] for i in breakfast}
        assert "breakfast_dish" in roles, f"breakfast roles: {roles}"
        assert roles <= {"breakfast_dish", "drink"}, f"breakfast roles: {roles}"

    def test_snack_5_meal_plan(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "meal_plan_type": "5", "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        items = resp.data["items"]
        snack1 = [i for i in items if i["meal_slot"] == "snack1"]
        snack2 = [i for i in items if i["meal_slot"] == "snack2"]
        # RB001_V_step4: snack1/snack2 = snack (+ drink опц.)
        assert "snack" in {i["component_role"] for i in snack1}
        assert {i["component_role"] for i in snack1} <= {"snack", "drink"}
        assert "snack" in {i["component_role"] for i in snack2}
        assert {i["component_role"] for i in snack2} <= {"snack", "drink"}

    def test_component_role_stored_in_db(self, client, setup_full):
        user, family, _ = setup_full
        client.force_authenticate(user)
        client.post(
            reverse("menu-generate"),
            {"period_days": 1},
            format="json",
        )
        items = MenuItem.objects.filter(menu__family=family)
        roles = set(items.values_list("component_role", flat=True))
        # RB001_V_step4: основное блюдо всегда есть
        assert "main" in roles
        assert "breakfast_dish" in roles
        assert "other" not in roles, f"unexpected 'other' in roles: {roles}"


@pytest.mark.django_db
class TestEmptyRolePool:
    def test_no_vegetable_recipes_returns_400(self, client, db):
        """RB001_V_step4: нет рецептов dish_type=main — 400 (обязательная роль)."""
        user = User.objects.create_user(email="empty@example.com", name="Пустой", password="pass1234")
        family = Family.objects.create(owner=user, name="Без главного")
        _attach_premium(family)
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        # есть завтрак, суп, салат, перекус — но НЕТ main
        for i in range(3):
            _mk_recipe(f"Завтрак {i}", "grain", dish_type="breakfast_dish")
            _mk_recipe(f"Суп {i}", "vegetable", dish_type="soup")
            _mk_recipe(f"Салат {i}", "vegetable", dish_type="salad")
            _mk_recipe(f"Перекус {i}", "fruit", dish_type="snack")

        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert resp.status_code == 400
        body = resp.data
        assert body["error"] == "empty_role_pool"
        assert "Не удалось подобрать" in body["message"]
        assert body["details"]["role"] == "main"

    def test_empty_pool_writes_audit_log(self, client, db):
        user = User.objects.create_user(email="audit@example.com", name="Аудит", password="pass1234")
        family = Family.objects.create(owner=user, name="Аудит-семья")
        _attach_premium(family)
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        for i in range(3):
            _mk_recipe(f"Завтрак {i}", "grain", dish_type="breakfast_dish")
            _mk_recipe(f"Суп {i}", "vegetable", dish_type="soup")
            _mk_recipe(f"Салат {i}", "vegetable", dish_type="salad")
            _mk_recipe(f"Перекус {i}", "fruit", dish_type="snack")

        before = AuditLog.objects.filter(action="menu.generate.empty_role_pool").count()
        client.force_authenticate(user)
        client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        after = AuditLog.objects.filter(action="menu.generate.empty_role_pool").count()
        assert after == before + 1

    def test_no_menu_saved_on_error(self, client, db):
        """При ошибке меню не должно появиться в БД."""
        from apps.menu.models import Menu

        user = User.objects.create_user(email="rollback@example.com", name="Ролл", password="pass1234")
        family = Family.objects.create(owner=user, name="Ролл-семья")
        _attach_premium(family)
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        for i in range(3):
            _mk_recipe(f"Завтрак {i}", "grain", dish_type="breakfast_dish")
            _mk_recipe(f"Суп {i}", "vegetable", dish_type="soup")
            _mk_recipe(f"Салат {i}", "vegetable", dish_type="salad")
            _mk_recipe(f"Перекус {i}", "fruit", dish_type="snack")

        before = Menu.objects.filter(family=family).count()
        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert resp.status_code == 400
        after = Menu.objects.filter(family=family).count()
        assert after == before


from datetime import timedelta as _MG606_td  # noqa: E402
from decimal import Decimal as _MG606_D  # noqa: E402

from django.utils import timezone as _MG606_tz  # noqa: E402

# MG-606.C: автоматический Premium для тестовых семей
from apps.subscriptions.models import Subscription as _MG606_Sub  # noqa: E402
from apps.subscriptions.models import SubscriptionPlan as _MG606_Plan  # noqa: E402


def _attach_premium(family):
    plan, _ = _MG606_Plan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": _MG606_D("0")},
    )
    if _MG606_Sub.objects.filter(family=family, plan=plan).exists():
        return
    _MG606_Sub.objects.create(
        family=family,
        plan=plan,
        status=_MG606_Sub.Status.ACTIVE,
        started_at=_MG606_tz.now() - _MG606_td(days=1),
        expires_at=_MG606_tz.now() + _MG606_td(days=365),
    )
