# MG_602_V_tests
"""
MG-602: целенаправленное покрытие apps/menu/views.py (67% → 80%+).

Покрываем helpers и view-классы, не покрытые ранее:
- _can_edit_menu / _can_delete_menu (все ветви)
- _check_allergens / _recipe_calories edge-кейсы
- _menu_snapshot
- MenuGenerateView: нет семьи, фильтры
- MenuListView / MenuDetailView: get_queryset без семьи / swagger_fake_view
- MenuDeleteView (целиком — все ветви)
- DeletedMenuListView (целиком)
- MenuRestoreView (целиком)
- MenuItemSwapView: 404/403/food_group/calorie_warning
- MenuArchiveView (целиком)
- ShoppingListView / ShoppingItemToggleView (целиком)
- _build_shopping_list: fridge skip, bad quantity
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem
from apps.menu.models import (
    DeletedMenu,
    Menu,
    MenuItem,
    ShoppingItem,
    ShoppingList,
)
from apps.menu import views as menu_views
from apps.recipes.models import Recipe
from apps.users.models import User


# ───────── helpers ────────────────────────────────────────────────────────
@pytest.fixture
def client():
    return APIClient()


def _mk_user(email="u@example.com", name="Юзер", user_type="user", **extra):
    return User.objects.create_user(
        email=email, name=name, password="x12345", user_type=user_type, **extra
    )


def _mk_family(user, role=None):
    fam = Family.objects.create(owner=user, name=f"Семья {user.name}")
    _attach_premium(fam)
    member = FamilyMember.objects.create(
        family=fam, user=user, role=role or FamilyMember.Role.HEAD
    )
    return fam, member


def _mk_recipe(title="Рец", **extra):
    defaults = dict(
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "Шаг"}],
        nutrition={"calories": {"value": "300", "unit": "ккал"}},
        categories=["Завтраки"],
        is_published=True,
    )
    defaults.update(extra)
    return Recipe.objects.create(title=title, **defaults)


@pytest.fixture
def setup(db):
    """Базовая фикстура: пользователь + семья + 30 рецептов."""
    user = _mk_user(email="m@example.com", name="Мама")
    fam, member = _mk_family(user)
    for i in range(30):
        _mk_recipe(title=f"Рецепт {i}",
                   nutrition={"calories": {"value": str(300 + i * 10), "unit": "ккал"}})
    return user, fam, member


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ HELPERS                                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestHelpers:
    def test_can_edit_menu_admin(self):
        admin = _mk_user(email="a@x.com", name="A", user_type="admin")
        # admin не обязан быть в семье
        fam = Family.objects.create(owner=admin, name="X")
        _attach_premium(fam)
        assert menu_views._can_edit_menu(admin, fam) is True

    def test_can_edit_menu_head(self, db):
        u = _mk_user(email="h@x.com", name="H")
        fam, _ = _mk_family(u, role=FamilyMember.Role.HEAD)
        assert menu_views._can_edit_menu(u, fam) is True

    def test_can_edit_menu_member_returns_false(self, db):
        u = _mk_user(email="m1@x.com", name="M")
        fam, _ = _mk_family(u, role=FamilyMember.Role.MEMBER)
        # MG_602: после удаления can_edit_menu обычный member не редактирует
        assert menu_views._can_edit_menu(u, fam) is False

    def test_can_edit_menu_no_membership(self, db):
        u = _mk_user(email="nm@x.com", name="NM")
        other = _mk_user(email="o@x.com", name="O")
        fam = Family.objects.create(owner=other, name="O")
        _attach_premium(fam)
        assert menu_views._can_edit_menu(u, fam) is False

    def test_can_delete_menu_admin(self, db):
        admin = _mk_user(email="ad@x.com", name="AD", user_type="admin")
        owner = _mk_user(email="ow@x.com", name="OW")
        fam, _ = _mk_family(owner)
        menu = Menu.objects.create(family=fam, creator_id=owner.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        assert menu_views._can_delete_menu(admin, fam, menu) is True

    def test_can_delete_menu_creator(self, db):
        u = _mk_user(email="cr@x.com", name="CR")
        fam, _ = _mk_family(u)
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        assert menu_views._can_delete_menu(u, fam, menu) is True

    def test_can_delete_menu_head_not_creator(self, db):
        head = _mk_user(email="hd@x.com", name="HD")
        other = _mk_user(email="ot@x.com", name="OT")
        fam, _ = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=other, role=FamilyMember.Role.MEMBER)
        menu = Menu.objects.create(family=fam, creator_id=other.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        assert menu_views._can_delete_menu(head, fam, menu) is True

    def test_can_delete_menu_member_not_creator_returns_false(self, db):
        head = _mk_user(email="hd2@x.com", name="HD")
        member = _mk_user(email="me@x.com", name="ME")
        fam, _ = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=member, role=FamilyMember.Role.MEMBER)
        menu = Menu.objects.create(family=fam, creator_id=head.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        assert menu_views._can_delete_menu(member, fam, menu) is False

    def test_check_allergens_finds_match(self, db):
        recipe = _mk_recipe(ingredients=[
            {"name": "Молоко 3.2%", "quantity": "200", "unit": "мл"},
            {"name": "Мука", "quantity": "100", "unit": "г"},
        ])
        found = menu_views._check_allergens(recipe, {"молоко"})
        assert "молоко" in found

    def test_check_allergens_empty_set(self, db):
        recipe = _mk_recipe()
        assert menu_views._check_allergens(recipe, set()) == []

    def test_check_allergens_no_dup(self, db):
        recipe = _mk_recipe(ingredients=[
            {"name": "Молоко", "quantity": "100", "unit": "мл"},
            {"name": "Молоко сгущ.", "quantity": "50", "unit": "г"},
        ])
        found = menu_views._check_allergens(recipe, {"молоко"})
        assert found.count("молоко") == 1

    def test_recipe_calories_typeerror_returns_zero(self, db):
        recipe = _mk_recipe(nutrition={"calories": "not-a-dict"})
        assert menu_views._recipe_calories(recipe) == 0.0

    def test_recipe_calories_value_error_returns_zero(self, db):
        recipe = _mk_recipe(nutrition={"calories": {"value": "abc"}})
        assert menu_views._recipe_calories(recipe) == 0.0

    def test_recipe_calories_normal(self, db):
        recipe = _mk_recipe(nutrition={"calories": {"value": "350"}})
        assert menu_views._recipe_calories(recipe) == 350.0

    def test_collect_allergens_from_family(self, db):
        u = _mk_user(email="al@x.com", name="AL", allergies=["орехи", "молоко"])
        fam, _ = _mk_family(u)
        result = menu_views._collect_allergens(fam)
        assert "орехи" in result
        assert "молоко" in result

    def test_collect_allergens_skips_non_list(self, db):
        u = _mk_user(email="bad@x.com", name="B")
        u.allergies = "not-a-list"
        u.save()
        fam, _ = _mk_family(u)
        result = menu_views._collect_allergens(fam)
        assert result == set()

    def test_menu_snapshot_with_items(self, db):
        u = _mk_user(email="sn@x.com", name="SN")
        fam, member = _mk_family(u)
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        recipe = _mk_recipe()
        MenuItem.objects.create(menu=menu, recipe=recipe, member=member,
                                meal_type="breakfast", day_offset=0)
        snap = menu_views._menu_snapshot(menu)
        assert snap["period_days"] == 1
        assert len(snap["items"]) == 1
        assert "meal_slot" in snap["items"][0]
        assert "component_role" in snap["items"][0]
        assert "is_cheat_meal" in snap["items"][0]


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ MenuGenerateView — негативные ветви                                     ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestMenuGenerateNegative:
    def test_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → нет Premium → 403 от gate (раньше: 404 из view).
        u = _mk_user(email="nf@x.com", name="NF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-generate"),
                           {"period_days": 1, "start_date": str(datetime.date.today())},
                           format="json")
        assert resp.status_code == 403

    def test_with_max_cook_time_filter(self, client, setup):
        user, _, _ = setup
        Recipe.objects.all().update(cook_time=20)
        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"),
                           {"period_days": 1, "max_cook_time": 30},
                           format="json")
        assert resp.status_code == 201

    def test_with_calorie_min_max_filters(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"),
                           {"period_days": 1, "calorie_min": 100, "calorie_max": 5000},
                           format="json")
        assert resp.status_code == 201


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ MenuListView / MenuDetailView                                           ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestMenuListDetail:
    def test_list_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → нет Premium → 403 от gate (раньше: 200 + пустой список).
        u = _mk_user(email="nfl@x.com", name="NFL")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-list"))
        assert resp.status_code == 403

    def test_detail_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="nfd@x.com", name="NFD")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-detail", args=[1]))
        assert resp.status_code == 403

    def test_list_get_queryset_swagger_fake(self, db):
        view = menu_views.MenuListView()
        view.swagger_fake_view = True
        view.request = type("R", (), {"user": None})()
        assert view.get_queryset().count() == 0

    def test_detail_get_queryset_swagger_fake(self, db):
        view = menu_views.MenuDetailView()
        view.swagger_fake_view = True
        view.request = type("R", (), {"user": None})()
        assert view.get_queryset().count() == 0


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ MenuDeleteView                                                          ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestMenuDelete:
    def test_delete_success(self, client, setup):
        user, fam, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        resp = client.delete(reverse("menu-delete", args=[menu_id]))
        assert resp.status_code == 204
        assert not Menu.objects.filter(id=menu_id).exists()
        assert DeletedMenu.objects.filter(family=fam).count() == 1

    def test_delete_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="dnf@x.com", name="DNF")
        client.force_authenticate(u)
        resp = client.delete(reverse("menu-delete", args=[999]))
        assert resp.status_code == 403

    def test_delete_menu_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.delete(reverse("menu-delete", args=[99999]))
        assert resp.status_code == 404

    def test_delete_no_permission_returns_403(self, client, db):
        head = _mk_user(email="hd3@x.com", name="HD")
        member = _mk_user(email="me3@x.com", name="ME")
        fam, _ = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=member, role=FamilyMember.Role.MEMBER)
        # Меню создал head, а удалить пытается member (не creator, не head)
        menu = Menu.objects.create(family=fam, creator_id=head.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        client.force_authenticate(member)
        resp = client.delete(reverse("menu-delete", args=[menu.id]))
        assert resp.status_code == 403


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ DeletedMenuListView + MenuRestoreView                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestDeletedAndRestore:
    def test_quarantine_list_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="qnf@x.com", name="QNF")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 403

    def test_quarantine_list_success(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        client.delete(reverse("menu-delete", args=[gen.data["id"]]))
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_restore_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="rnf@x.com", name="RNF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-restore", args=[999]))
        assert resp.status_code == 403

    def test_restore_deleted_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("menu-restore", args=[99999]))
        assert resp.status_code == 404

    def test_restore_success(self, client, setup):
        user, fam, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        client.delete(reverse("menu-delete", args=[menu_id]))
        deleted = DeletedMenu.objects.get(family=fam)
        resp = client.post(reverse("menu-restore", args=[deleted.id]))
        assert resp.status_code == 201
        assert resp.data["period_days"] == 1
        assert not DeletedMenu.objects.filter(id=deleted.id).exists()

    def test_restore_skips_missing_recipe(self, client, setup):
        user, fam, member = setup
        client.force_authenticate(user)
        # делаем DeletedMenu вручную с несуществующим recipe_id в snapshot
        DeletedMenu.objects.create(
            menu_id=999,
            family=fam,
            deleted_by=user,
            data={
                "id": 999,
                "start_date": str(datetime.date.today()),
                "end_date": str(datetime.date.today()),
                "period_days": 1,
                "status": "active",
                "filters_used": {},
                "items": [
                    {"recipe_id": 99999, "member_id": member.id,
                     "meal_type": "breakfast", "day_offset": 0,
                     "meal_slot": "breakfast", "component_role": "other",
                     "is_cheat_meal": False, "quantity": "1.0"},
                ],
            },
            purge_after=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        )
        deleted = DeletedMenu.objects.filter(family=fam).first()
        resp = client.post(reverse("menu-restore", args=[deleted.id]))
        assert resp.status_code == 201

    def test_restore_no_permission_403(self, client, db):
        head = _mk_user(email="rhd@x.com", name="RHD")
        member = _mk_user(email="rme@x.com", name="RME")
        fam, _ = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=member, role=FamilyMember.Role.MEMBER)
        # DeletedMenu, deleted_by=head, restore пробует member
        deleted = DeletedMenu.objects.create(
            menu_id=1, family=fam, deleted_by=head,
            data={"items": [], "period_days": 1,
                  "start_date": str(datetime.date.today()),
                  "end_date": str(datetime.date.today()),
                  "filters_used": {}},
            purge_after=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        )
        client.force_authenticate(member)
        resp = client.post(reverse("menu-restore", args=[deleted.id]))
        assert resp.status_code == 403


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ MenuItemSwapView                                                        ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestMenuItemSwap:
    def test_swap_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="snf@x.com", name="SNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[1, 1]),
                            {"recipe_id": 1}, format="json")
        assert resp.status_code == 403

    def test_swap_no_permission_403(self, client, db):
        head = _mk_user(email="shd@x.com", name="SHD")
        member = _mk_user(email="sme@x.com", name="SME")
        fam, head_m = _mk_family(head)
        FamilyMember.objects.create(family=fam, user=member, role=FamilyMember.Role.MEMBER)
        recipe = _mk_recipe()
        menu = Menu.objects.create(family=fam, creator_id=head.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        item = MenuItem.objects.create(menu=menu, recipe=recipe, member=head_m,
                                       meal_type="breakfast", day_offset=0)
        client.force_authenticate(member)
        resp = client.patch(reverse("menu-item-swap", args=[menu.id, item.id]),
                            {"recipe_id": recipe.id}, format="json")
        assert resp.status_code == 403

    def test_swap_menu_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.patch(reverse("menu-item-swap", args=[99999, 1]),
                            {"recipe_id": 1}, format="json")
        assert resp.status_code == 404

    def test_swap_recipe_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        item_id = gen.data["items"][0]["id"]
        resp = client.patch(reverse("menu-item-swap", args=[menu_id, item_id]),
                            {"recipe_id": 99999}, format="json")
        assert resp.status_code == 404

    def test_swap_different_food_group_400(self, client, db):
        u = _mk_user(email="fg@x.com", name="FG")
        fam, member = _mk_family(u)
        recipe_a = _mk_recipe(title="Овощи", food_group="vegetable")
        recipe_b = _mk_recipe(title="Мясо", food_group="protein")
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        item = MenuItem.objects.create(menu=menu, recipe=recipe_a, member=member,
                                       meal_type="lunch", day_offset=0)
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[menu.id, item.id]),
                            {"recipe_id": recipe_b.id}, format="json")
        assert resp.status_code == 400

    def test_swap_calorie_min_warning(self, client, db):
        u = _mk_user(email="cm@x.com", name="CM")
        fam, member = _mk_family(u)
        rec_a = _mk_recipe(title="A",
                           nutrition={"calories": {"value": "500"}})
        rec_b = _mk_recipe(title="B",
                           nutrition={"calories": {"value": "10"}})
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today(),
                                   filters_used={"calorie_min": 2000})
        item = MenuItem.objects.create(menu=menu, recipe=rec_a, member=member,
                                       meal_type="lunch", day_offset=0)
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[menu.id, item.id]),
                            {"recipe_id": rec_b.id}, format="json")
        assert resp.status_code == 200
        assert resp.data["calorie_warning"] is True

    def test_swap_calorie_max_warning(self, client, db):
        u = _mk_user(email="cmax@x.com", name="CMAX")
        fam, member = _mk_family(u)
        rec_a = _mk_recipe(title="A",
                           nutrition={"calories": {"value": "300"}})
        rec_b = _mk_recipe(title="B",
                           nutrition={"calories": {"value": "9999"}})
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today(),
                                   filters_used={"calorie_max": 1000})
        item = MenuItem.objects.create(menu=menu, recipe=rec_a, member=member,
                                       meal_type="lunch", day_offset=0)
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[menu.id, item.id]),
                            {"recipe_id": rec_b.id}, format="json")
        assert resp.status_code == 200
        assert resp.data["calorie_warning"] is True

    def test_swap_allergen_warning(self, client, db):
        u = _mk_user(email="alg@x.com", name="ALG", allergies=["орех"])
        fam, member = _mk_family(u)
        rec_a = _mk_recipe(title="A")
        rec_b = _mk_recipe(title="B", ingredients=[
            {"name": "Грецкий орех", "quantity": "50", "unit": "г"},
        ])
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        item = MenuItem.objects.create(menu=menu, recipe=rec_a, member=member,
                                       meal_type="lunch", day_offset=0)
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[menu.id, item.id]),
                            {"recipe_id": rec_b.id}, format="json")
        assert resp.status_code == 200
        assert resp.data["allergen_warning"] is True
        assert "орех" in resp.data["allergens_found"]


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ MenuArchiveView                                                         ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestMenuArchive:
    def test_archive_success(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        resp = client.post(reverse("menu-archive", args=[menu_id]))
        assert resp.status_code == 200
        assert Menu.objects.get(id=menu_id).status == Menu.Status.ARCHIVED

    def test_archive_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("menu-archive", args=[99999]))
        assert resp.status_code == 404


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ ShoppingListView + ShoppingItemToggleView                               ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestShopping:
    def test_shopping_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="snf2@x.com", name="SNF2")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-shopping-list", args=[1]))
        assert resp.status_code == 403

    def test_shopping_menu_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("menu-shopping-list", args=[99999]))
        assert resp.status_code == 404

    def test_shopping_list_build_success(self, client, setup):
        user, fam, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        resp = client.get(reverse("menu-shopping-list", args=[menu_id]))
        assert resp.status_code == 200
        assert "items" in resp.data
        assert ShoppingList.objects.filter(menu_id=menu_id).exists()

    def test_shopping_list_skips_fridge_items(self, client, db):
        u = _mk_user(email="fr@x.com", name="FR")
        fam, member = _mk_family(u)
        recipe = _mk_recipe(ingredients=[
            {"name": "Молоко", "quantity": "100", "unit": "мл"},
            {"name": "Мука", "quantity": "200", "unit": "г"},
        ])
        FridgeItem.objects.create(family=fam, name="Молоко", quantity=Decimal("500"),
                                  unit="мл", is_deleted=False)
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        MenuItem.objects.create(menu=menu, recipe=recipe, member=member,
                                meal_type="breakfast", day_offset=0)
        client.force_authenticate(u)
        resp = client.get(reverse("menu-shopping-list", args=[menu.id]))
        assert resp.status_code == 200
        names = [i["name"] for i in resp.data["items"]]
        assert "Мука" in names
        assert "Молоко" not in names

    def test_shopping_list_handles_bad_quantity(self, client, db):
        u = _mk_user(email="bq@x.com", name="BQ")
        fam, member = _mk_family(u)
        recipe = _mk_recipe(ingredients=[
            {"name": "Соль", "quantity": "по вкусу", "unit": "г"},
        ])
        menu = Menu.objects.create(family=fam, creator_id=u.id, period_days=1,
                                   start_date=datetime.date.today(),
                                   end_date=datetime.date.today())
        MenuItem.objects.create(menu=menu, recipe=recipe, member=member,
                                meal_type="breakfast", day_offset=0)
        client.force_authenticate(u)
        resp = client.get(reverse("menu-shopping-list", args=[menu.id]))
        assert resp.status_code == 200

    def test_toggle_item_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="tnf@x.com", name="TNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("shopping-item-toggle", args=[1, 1]))
        assert resp.status_code == 403

    def test_toggle_item_not_found(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.patch(reverse("shopping-item-toggle", args=[99999, 99999]))
        assert resp.status_code == 404

    def test_toggle_item_success_on_off(self, client, setup):
        user, fam, _ = setup
        client.force_authenticate(user)
        gen = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        menu_id = gen.data["id"]
        resp = client.get(reverse("menu-shopping-list", args=[menu_id]))
        assert resp.data["items"], "shopping list пустой"
        item_id = resp.data["items"][0]["id"]
        # toggle ON
        r1 = client.patch(reverse("shopping-item-toggle", args=[menu_id, item_id]))
        assert r1.status_code == 200
        assert r1.data["is_purchased"] is True
        # toggle OFF
        r2 = client.patch(reverse("shopping-item-toggle", args=[menu_id, item_id]))
        assert r2.status_code == 200
        assert r2.data["is_purchased"] is False


# MG-606.C: автоматический Premium для тестовых семей
from apps.subscriptions.models import Subscription as _MG606_Sub, SubscriptionPlan as _MG606_Plan
from decimal import Decimal as _MG606_D
from django.utils import timezone as _MG606_tz
from datetime import timedelta as _MG606_td


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
