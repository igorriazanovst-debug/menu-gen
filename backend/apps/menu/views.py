import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription

from .generator import MenuGenerator
from .models import DeletedMenu, Menu, MenuItem, ShoppingItem, ShoppingList
from .serializers import (
    DeletedMenuSerializer,
    GenerateMenuSerializer,
    MenuDetailSerializer,
    MenuItemSwapSerializer,
    MenuListSerializer,
    ShoppingItemSerializer,
    ShoppingListSerializer,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_family(user):
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    return membership.family if membership else None


def _get_plan_code(family) -> str:
    sub = (
        Subscription.objects.filter(family=family, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .order_by("-started_at")
        .first()
    )
    return sub.plan.code if sub else "free"


def _can_edit_menu(user, family):
    """Может редактировать: head семьи, admin, или член с can_edit_menu=True."""
    if user.user_type == "admin":
        return True
    m = FamilyMember.objects.filter(family=family, user=user).first()
    if not m:
        return False
    return m.role == FamilyMember.Role.HEAD or m.can_edit_menu


def _can_delete_menu(user, family, menu):
    """Может удалять: создатель меню или head/admin."""
    if user.user_type == "admin":
        return True
    if menu.creator_id == user.id:
        return True
    m = FamilyMember.objects.filter(family=family, user=user).first()
    return m and m.role == FamilyMember.Role.HEAD


def _collect_allergens(family):
    """Все аллергены из профилей семьи (объединение)."""
    allergens = set()
    for m in FamilyMember.objects.filter(family=family).select_related("user"):
        if isinstance(m.user.allergies, list):
            allergens.update(a.lower() for a in m.user.allergies)
    return allergens


def _check_allergens(recipe, allergens):
    """Возвращает список аллергенов, найденных в рецепте."""
    if not allergens:
        return []
    found = []
    for ing in recipe.ingredients:
        name = ing.get("name", "").lower()
        for a in allergens:
            if a in name and a not in found:
                found.append(a)
    return found


def _recipe_calories(recipe):
    try:
        return float(recipe.nutrition.get("calories", {}).get("value", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _menu_snapshot(menu):
    items = []
    for item in MenuItem.objects.filter(menu=menu).select_related("recipe", "member__user"):
        items.append({
            "id": item.id,
            "day_offset": item.day_offset,
            "meal_type": item.meal_type,
            "recipe_id": item.recipe_id,
            "recipe_title": item.recipe.title,
            "member_id": item.member_id,
            "quantity": str(item.quantity),
        })
    return {
        "id": menu.id,
        "start_date": str(menu.start_date),
        "end_date": str(menu.end_date),
        "period_days": menu.period_days,
        "status": menu.status,
        "filters_used": menu.filters_used,
        "items": items,
    }


# ── views ─────────────────────────────────────────────────────────────────────

class MenuGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=GenerateMenuSerializer, responses={201: MenuDetailSerializer})
    def post(self, request):
        serializer = GenerateMenuSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        plan_code = _get_plan_code(family)
        start_date = data["start_date"]
        period_days = data["period_days"]

        member_ids = data.get("member_ids")
        all_members = FamilyMember.objects.filter(family=family).select_related("user", "user__profile")
        members = all_members.filter(id__in=member_ids) if member_ids else all_members

        filters = {}
        if data.get("country"):
            filters["country"] = data["country"]
        if data.get("max_cook_time"):
            filters["max_cook_time"] = data["max_cook_time"]
        if data.get("calorie_min"):
            filters["calorie_min"] = data["calorie_min"]
        if data.get("calorie_max"):
            filters["calorie_max"] = data["calorie_max"]

        generator = MenuGenerator(
            family=family,
            members=members,
            period_days=period_days,
            start_date=start_date,
            plan_code=plan_code,
            filters=filters,
        )
        generated = generator.generate()

        with transaction.atomic():
            menu = Menu.objects.create(
                family=family,
                creator_id=request.user.id,
                period_days=period_days,
                start_date=start_date,
                end_date=start_date + timedelta(days=period_days - 1),
                status=Menu.Status.ACTIVE,
                filters_used=filters,
            )
            MenuItem.objects.bulk_create([
                MenuItem(
                    menu=menu,
                    recipe=item["recipe"],
                    member=item["member"],
                    meal_type=item["meal_type"],
                    day_offset=item["day_offset"],
                )
                for item in generated
            ])

        menu_full = Menu.objects.prefetch_related("items__recipe", "items__member__user").get(id=menu.id)
        return Response(MenuDetailSerializer(menu_full).data, status=status.HTTP_201_CREATED)


class MenuListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MenuListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Menu.objects.none()
        family = _get_family(self.request.user)
        if not family:
            return Menu.objects.none()
        return Menu.objects.filter(
            family=family,
            status__in=[Menu.Status.ACTIVE, Menu.Status.DRAFT],
        ).order_by("-generated_at")


class MenuDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MenuDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Menu.objects.none()
        family = _get_family(self.request.user)
        if not family:
            return Menu.objects.none()
        return Menu.objects.filter(family=family).prefetch_related("items__recipe", "items__member__user")


class MenuDeleteView(APIView):
    """Мягкое удаление — перемещение в карантин на 24ч."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, menu_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            menu = Menu.objects.get(id=menu_id, family=family)
        except Menu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not _can_delete_menu(request.user, family, menu):
            return Response({"detail": "Нет прав на удаление."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        DeletedMenu.objects.create(
            menu_id=menu.id,
            family=family,
            deleted_by=request.user,
            data=_menu_snapshot(menu),
            purge_after=now + timedelta(hours=24),
        )
        menu.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeletedMenuListView(APIView):
    """Список меню в карантине для текущей семьи."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        items = DeletedMenu.objects.filter(family=family)
        return Response(DeletedMenuSerializer(items, many=True).data)


class MenuRestoreView(APIView):
    """Восстановление меню из карантина (до истечения 24ч)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, deleted_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            deleted = DeletedMenu.objects.get(id=deleted_id, family=family)
        except DeletedMenu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not _can_delete_menu(request.user, family, type("M", (), {"creator_id": deleted.deleted_by_id})() ):
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)

        snap = deleted.data
        with transaction.atomic():
            menu = Menu.objects.create(
                family=family,
                creator_id=deleted.deleted_by_id or request.user.id,
                period_days=snap["period_days"],
                start_date=snap["start_date"],
                end_date=snap["end_date"],
                status=Menu.Status.ACTIVE,
                filters_used=snap.get("filters_used", {}),
            )
            for item in snap.get("items", []):
                try:
                    recipe = Recipe.objects.get(id=item["recipe_id"])
                    member = FamilyMember.objects.filter(id=item.get("member_id")).first()
                    MenuItem.objects.create(
                        menu=menu,
                        recipe=recipe,
                        member=member,
                        meal_type=item["meal_type"],
                        day_offset=item["day_offset"],
                    )
                except Recipe.DoesNotExist:
                    pass
            deleted.delete()

        menu_full = Menu.objects.prefetch_related("items__recipe", "items__member__user").get(id=menu.id)
        return Response(MenuDetailSerializer(menu_full).data, status=status.HTTP_201_CREATED)


class MenuItemSwapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=MenuItemSwapSerializer, responses={200: None})
    def patch(self, request, menu_id, item_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not _can_edit_menu(request.user, family):
            return Response({"detail": "Нет прав на редактирование меню."}, status=status.HTTP_403_FORBIDDEN)

        try:
            menu = Menu.objects.get(id=menu_id, family=family)
            item = MenuItem.objects.select_related("recipe").get(id=item_id, menu=menu)
        except (Menu.DoesNotExist, MenuItem.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = MenuItemSwapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            recipe = Recipe.objects.get(id=serializer.validated_data["recipe_id"], is_published=True)
        except Recipe.DoesNotExist:
            return Response({"detail": "Рецепт не найден."}, status=status.HTTP_404_NOT_FOUND)

        item.recipe = recipe
        item.save(update_fields=["recipe"])
        menu.modified_by = Menu.ModifiedBy.USER
        menu.save(update_fields=["modified_by", "updated_at"])

        # ── проверки предупреждений ───────────────────────────────────────
        allergens = _collect_allergens(family)
        found_allergens = _check_allergens(recipe, allergens)
        allergen_warning = len(found_allergens) > 0

        calorie_warning = False
        filters = menu.filters_used or {}
        cal = _recipe_calories(recipe)
        if filters.get("calorie_min") and cal > 0 and cal < float(filters["calorie_min"]) / 4:
            calorie_warning = True
        if filters.get("calorie_max") and cal > 0 and cal > float(filters["calorie_max"]) / 4:
            calorie_warning = True

        return Response({
            "allergen_warning": allergen_warning,
            "allergens_found": found_allergens,
            "calorie_warning": calorie_warning,
            "recipe_calories": cal,
        }, status=status.HTTP_200_OK)


class MenuArchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: None})
    def post(self, request, menu_id):
        family = _get_family(request.user)
        try:
            menu = Menu.objects.get(id=menu_id, family=family)
        except Menu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        menu.status = Menu.Status.ARCHIVED
        menu.save(update_fields=["status"])
        return Response(status=status.HTTP_200_OK)


class ShoppingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ShoppingListSerializer})
    def get(self, request, menu_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            menu = Menu.objects.get(id=menu_id, family=family)
        except Menu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        shopping_list, created = ShoppingList.objects.get_or_create(family=family, menu=menu)
        if created:
            _build_shopping_list(shopping_list, menu, family)

        shopping_list = ShoppingList.objects.prefetch_related("items").get(id=shopping_list.id)
        return Response(ShoppingListSerializer(shopping_list).data)


class ShoppingItemToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ShoppingItemSerializer})
    def patch(self, request, menu_id, item_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            shopping_list = ShoppingList.objects.get(menu_id=menu_id, family=family)
            item = ShoppingItem.objects.get(id=item_id, shopping_list=shopping_list)
        except (ShoppingList.DoesNotExist, ShoppingItem.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)

        item.is_purchased = not item.is_purchased
        item.purchased_by_id = request.user.id if item.is_purchased else None
        item.save(update_fields=["is_purchased", "purchased_by_id"])
        return Response(ShoppingItemSerializer(item).data)


def _build_shopping_list(shopping_list: ShoppingList, menu: Menu, family: Family):
    from collections import defaultdict
    fridge = {i.name.lower() for i in FridgeItem.objects.filter(family=family, is_deleted=False)}
    aggregated = defaultdict(lambda: {"quantity": 0, "unit": ""})
    for menu_item in MenuItem.objects.filter(menu=menu).select_related("recipe"):
        for ing in menu_item.recipe.ingredients:
            name = ing.get("name", "").strip()
            if not name or name.lower() in fridge:
                continue
            key = name.lower()
            try:
                aggregated[key]["quantity"] += float(ing.get("quantity") or 0)
            except (TypeError, ValueError):
                pass
            aggregated[key]["unit"] = ing.get("unit", "")
            aggregated[key]["name"] = name

    items = [
        ShoppingItem(
            shopping_list=shopping_list,
            name=v["name"],
            quantity=v["quantity"] or None,
            unit=v["unit"] or None,
        )
        for v in aggregated.values()
    ]
    ShoppingItem.objects.bulk_create(items)
