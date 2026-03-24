from datetime import date, timedelta

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription

from .generator import MenuGenerator
from .models import Menu, MenuItem, ShoppingItem, ShoppingList
from .serializers import (
    GenerateMenuSerializer,
    MenuDetailSerializer,
    MenuItemSwapSerializer,
    MenuListSerializer,
    ShoppingItemSerializer,
    ShoppingListSerializer,
)


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

        # Определяем состав участников
        member_ids = data.get("member_ids")
        all_members = FamilyMember.objects.filter(family=family).select_related(
            "user", "user__profile"
        )
        if member_ids:
            members = all_members.filter(id__in=member_ids)
        else:
            members = all_members

        filters = {}
        if data.get("country"):
            filters["country"] = data["country"]
        if data.get("max_cook_time"):
            filters["max_cook_time"] = data["max_cook_time"]

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

        menu_full = Menu.objects.prefetch_related(
            "items__recipe", "items__member__user"
        ).get(id=menu.id)
        return Response(MenuDetailSerializer(menu_full).data, status=status.HTTP_201_CREATED)


class MenuListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MenuListSerializer

    def get_queryset(self):
        family = _get_family(self.request.user)
        if not family:
            return Menu.objects.none()
        return Menu.objects.filter(family=family).order_by("-generated_at")


class MenuDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MenuDetailSerializer

    def get_queryset(self):
        family = _get_family(self.request.user)
        if not family:
            return Menu.objects.none()
        return Menu.objects.filter(family=family).prefetch_related(
            "items__recipe", "items__member__user"
        )


class MenuItemSwapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=MenuItemSwapSerializer, responses={200: None})
    def patch(self, request, menu_id, item_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            menu = Menu.objects.get(id=menu_id, family=family)
            item = MenuItem.objects.get(id=item_id, menu=menu)
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

        return Response(status=status.HTTP_200_OK)


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

        # Используем уже созданный или строим новый
        shopping_list, created = ShoppingList.objects.get_or_create(
            family=family, menu=menu
        )
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


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_shopping_list(shopping_list: ShoppingList, menu: Menu, family: Family):
    """
    Суммирует ингредиенты меню, вычитает продукты из холодильника,
    записывает недостающее в ShoppingItem.
    """
    # 1. Собираем все ингредиенты из рецептов меню
    aggregated: dict = {}  # (name_lower, unit) -> {name, unit, category, quantity}

    for item in MenuItem.objects.filter(menu=menu).select_related("recipe"):
        for ing in item.recipe.ingredients:
            name = ing.get("name", "").strip()
            unit = ing.get("unit", "").strip()
            if not name:
                continue
            key = (name.lower(), unit.lower())
            try:
                qty = float(ing.get("quantity") or 0) * float(item.quantity)
            except (TypeError, ValueError):
                qty = 0
            if key in aggregated:
                aggregated[key]["quantity"] = aggregated[key]["quantity"] + qty
            else:
                aggregated[key] = {"name": name, "unit": unit, "category": "", "quantity": qty}

    # 2. Вычитаем холодильник
    fridge = {
        (fi.name.lower(), fi.unit.lower()): float(fi.quantity or 0)
        for fi in FridgeItem.objects.filter(family=family, is_deleted=False)
    }
    for key, data in aggregated.items():
        in_fridge = fridge.get(key, 0)
        data["quantity"] = max(0, data["quantity"] - in_fridge)

    # 3. Записываем в ShoppingItem (только qty > 0)
    items_to_create = []
    for data in aggregated.values():
        if data["quantity"] > 0:
            items_to_create.append(
                ShoppingItem(
                    shopping_list=shopping_list,
                    name=data["name"],
                    quantity=data["quantity"] if data["quantity"] else None,
                    unit=data["unit"],
                    category=data["category"],
                )
            )
    ShoppingItem.objects.bulk_create(items_to_create)
