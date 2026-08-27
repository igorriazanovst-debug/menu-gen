import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem, ShoppingItem, ShoppingList
from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="menu@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user, name="Семья")
    _attach_premium(family)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)

    for i in range(30):
        Recipe.objects.create(
            title=f"Рецепт {i}",
            ingredients=[{"name": f"Ингред {i}", "quantity": "100", "unit": "г"}],
            steps=[{"text": "Шаг 1"}],
            nutrition={"calories": {"value": str(300 + i * 10), "unit": "ккал"}},
            categories=["Завтраки"],
            is_published=True,
        )

    return user, family, member


@pytest.mark.django_db
class TestMenuGenerate:
    def test_generate_default(self, client, setup):
        user, family, member = setup
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 3, "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201
        assert "items" in resp.data
        assert len(resp.data["items"]) > 0

    def test_generate_creates_menu_in_db(self, client, setup):
        user, family, _ = setup
        client.force_authenticate(user)
        client.post(
            reverse("menu-generate"),
            {"period_days": 2},
            format="json",
        )
        assert Menu.objects.filter(family=family).count() == 1

    def test_generate_with_country_filter(self, client, setup):
        user, _, _ = setup
        Recipe.objects.all().update(country="Россия")
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "country": "Россия"},
            format="json",
        )
        assert resp.status_code == 201

    def test_generate_unauthenticated(self, client):
        resp = client.post(reverse("menu-generate"), {}, format="json")
        assert resp.status_code == 401

    def test_generate_invalid_period(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"), {"period_days": 0}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMenuList:
    def test_list_empty(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("menu-list"))
        assert resp.status_code == 200
        assert resp.data["count"] == 0

    def test_list_after_generate(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        resp = client.get(reverse("menu-list"))
        assert resp.data["count"] == 1


@pytest.mark.django_db
class TestMenuDetail:
    def test_detail(self, client, setup):
        user, family, member = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        resp = client.get(reverse("menu-detail", args=[menu_id]))
        assert resp.status_code == 200
        assert "items" in resp.data

    def test_detail_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("menu-detail", args=[99999]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestMenuItemSwap:
    def test_swap(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]
        new_recipe = Recipe.objects.last()
        resp = client.patch(
            reverse("menu-item-swap", args=[menu_id, item_id]),
            {"recipe_id": new_recipe.id},
            format="json",
        )
        assert resp.status_code == 200
        assert MenuItem.objects.get(id=item_id).recipe_id == new_recipe.id

    # MG_SWAPFREE: раньше замена на другую пищевую группу отклонялась с 400 —
    # рецепт было видно в разделе «Рецепты», но подставить его в меню не давало.
    def test_swap_на_другую_группу_разрешён_с_предупреждением(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]

        item = MenuItem.objects.get(id=item_id)
        item.recipe.food_group = "grain"  # «мини-панкейки»
        item.recipe.save(update_fields=["food_group"])
        other_group = Recipe.objects.create(
            title="Сырники солёные с сыром",
            food_group="protein",
            ingredients=[],
            steps=[],
            is_published=True,
        )

        resp = client.patch(
            reverse("menu-item-swap", args=[menu_id, item_id]),
            {"recipe_id": other_group.id},
            format="json",
        )

        assert resp.status_code == 200
        assert MenuItem.objects.get(id=item_id).recipe_id == other_group.id
        assert resp.data["food_group_warning"] is True
        assert resp.data["food_group_expected"] == "grain"
        assert resp.data["food_group_new"] == "protein"

    def test_swap_внутри_группы_без_предупреждения(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]

        item = MenuItem.objects.get(id=item_id)
        item.recipe.food_group = "grain"
        item.recipe.save(update_fields=["food_group"])
        same_group = Recipe.objects.create(
            title="Овсянка", food_group="grain", ingredients=[], steps=[], is_published=True
        )

        resp = client.patch(
            reverse("menu-item-swap", args=[menu_id, item_id]),
            {"recipe_id": same_group.id},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["food_group_warning"] is False

    def test_swap_без_группы_не_предупреждает(self, client, setup):
        """У рецепта может не быть food_group — это не повод пугать пользователя."""
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]
        no_group = Recipe.objects.create(
            title="Без группы", food_group=None, ingredients=[], steps=[], is_published=True
        )

        resp = client.patch(
            reverse("menu-item-swap", args=[menu_id, item_id]),
            {"recipe_id": no_group.id},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["food_group_warning"] is False

    def test_swap_nonexistent_recipe(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]
        resp = client.patch(
            reverse("menu-item-swap", args=[menu_id, item_id]),
            {"recipe_id": 99999},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestShoppingList:
    def test_shopping_list_created(self, client, setup):
        user, family, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 2}, format="json")
        menu_id = gen.data["id"]
        resp = client.get(reverse("menu-shopping-list", args=[menu_id]))
        assert resp.status_code == 200
        assert "items" in resp.data

    def test_shopping_list_idempotent(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        client.get(reverse("menu-shopping-list", args=[menu_id]))
        client.get(reverse("menu-shopping-list", args=[menu_id]))
        assert ShoppingList.objects.count() == 1

    def test_toggle_item(self, client, setup):
        user, family, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        client.get(reverse("menu-shopping-list", args=[menu_id]))
        item = ShoppingItem.objects.filter(shopping_list__menu_id=menu_id).first()
        if item:
            resp = client.patch(reverse("menu-shopping-item-toggle", args=[menu_id, item.id]))
            assert resp.status_code == 200
            item.refresh_from_db()
            assert item.is_purchased is True


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
