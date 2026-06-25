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
from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly
from apps.subscriptions.quota import (
    can_generate_menu,
    menu_quota_limit,
    menu_quota_reset_at,
    try_consume_menu_generation,
)

from .exceptions import MenuGeneratorError  # MG_301_V_views
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


def _quota_exceeded_payload(family) -> dict:
    """Тело ответа 403 при исчерпании бесплатной квоты генераций."""
    limit = menu_quota_limit(family)
    return {
        "detail": (
            f"Лимит бесплатных генераций меню исчерпан ({limit}/мес). " "Оформите Premium для безлимитной генерации."
        ),
        "code": "menu_quota_exceeded",
        "reset_at": menu_quota_reset_at(family).isoformat(),
    }


def _can_edit_menu(user, family):
    """MG_602_V_views: может редактировать: head семьи или admin (поле can_edit_menu удалено в family.0004)."""
    if user.user_type == "admin":
        return True
    m = FamilyMember.objects.filter(family=family, user=user).first()
    if not m:
        return False
    return m.role == FamilyMember.Role.HEAD


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
    # KBJU_DISPLAY: nutrition['calories'] может быть числом (плоский формат БД)
    # или dict {value, unit} (legacy). Поддерживаем оба.
    try:
        cal = (recipe.nutrition or {}).get("calories", 0)
        if isinstance(cal, dict):
            cal = cal.get("value", 0)
        return float(cal or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _menu_snapshot(menu):
    # MG_602_V_views: добавлены meal_slot, component_role, is_cheat_meal для корректного restore
    items = []
    for item in MenuItem.objects.filter(menu=menu).select_related("recipe", "member__user"):
        items.append(
            {
                "id": item.id,
                "day_offset": item.day_offset,
                "meal_type": item.meal_type,
                "meal_slot": item.meal_slot,
                "component_role": item.component_role,
                "is_cheat_meal": item.is_cheat_meal,
                "recipe_id": item.recipe_id,
                "recipe_title": item.recipe.title,
                "member_id": item.member_id,
                "quantity": str(item.quantity),
            }
        )
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
    # Freemium: генерация доступна и бесплатным семьям (в пределах квоты);
    # premium — без лимита. Сама проверка квоты — ниже, в post().
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=GenerateMenuSerializer, responses={201: MenuDetailSerializer})
    def post(self, request):
        serializer = GenerateMenuSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        # Freemium-квота: дешёвая предпроверка до дорогой генерации.
        if not can_generate_menu(family):
            return Response(_quota_exceeded_payload(family), status=status.HTTP_403_FORBIDDEN)

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
        # MG_610_V_generator: new filters
        filters["with_soup"] = data.get("with_soup", True)
        if data.get("countries"):
            filters["countries"] = data["countries"]
        if data.get("exclude_allergens") is not None:
            filters["exclude_allergens"] = data["exclude_allergens"]
        if data.get("exclude_disliked") is not None:
            filters["exclude_disliked"] = data["exclude_disliked"]
        if data.get("meal_plan_type"):
            filters["meal_plan_type"] = data["meal_plan_type"]
        if data.get("strategy"):
            filters["strategy"] = data["strategy"]  # MG_STRAT
        if data.get("mode"):
            filters["mode"] = data["mode"]

        # MG_605A_V_views: проброс mode (per_member | family)
        filters["mode"] = data.get("mode", "family")
        # MG_607_V_views: countries (мульти), exclude_allergens, exclude_disliked
        if data.get("countries"):
            filters["countries"] = list(data["countries"])
        if "exclude_allergens" in data:
            filters["exclude_allergens"] = list(data.get("exclude_allergens") or [])
        if "exclude_disliked" in data:
            filters["exclude_disliked"] = list(data.get("exclude_disliked") or [])

        generator = MenuGenerator(
            family=family,
            members=members,
            period_days=period_days,
            start_date=start_date,
            plan_code=plan_code,
            filters=filters,
        )
        try:
            generated = generator.generate()
        except MenuGeneratorError as exc:  # MG_301_V_views
            return Response(exc.to_response(), status=status.HTTP_400_BAD_REQUEST)

        # Списываем квоту под row-lock (select_for_update требует транзакцию) —
        # защита от гонки параллельных генераций у одной семьи. Premium → no-op.
        with transaction.atomic():
            if not try_consume_menu_generation(family):
                return Response(_quota_exceeded_payload(family), status=status.HTTP_403_FORBIDDEN)

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
            MenuItem.objects.bulk_create(
                [
                    MenuItem(
                        menu=menu,
                        recipe=item["recipe"],
                        member=item["member"],
                        meal_type=item["meal_type"],
                        meal_slot=item.get("meal_slot", item["meal_type"]),
                        day_offset=item["day_offset"],
                        component_role=item.get("component_role", "other"),
                        is_cheat_meal=item.get("is_cheat_meal", False),  # MG_505_V_views
                        quantity=item.get("quantity", 1),  # MG_605A_V_views
                    )
                    for item in generated
                ]
            )

            # MG_505_V_views: обновить last_cheat_meal_date для членов, у которых в этом меню был cheat
            from collections import defaultdict

            from apps.menu.generator import _mg505_mark_cheat_meal_used

            _mg505_seen = defaultdict(list)  # member_id -> list of (day_offset)
            for it in generated:
                if it.get("is_cheat_meal"):
                    m = it.get("member")
                    if m is not None:
                        _mg505_seen[m.id].append(it.get("day_offset", 0))
            for m in members:
                if m.id in _mg505_seen:
                    last_day = max(_mg505_seen[m.id])
                    from datetime import timedelta as _mg505_td

                    _mg505_mark_cheat_meal_used(m, start_date + _mg505_td(days=last_day))

        menu_full = Menu.objects.prefetch_related("items__recipe", "items__member__user").get(id=menu.id)
        return Response(MenuDetailSerializer(menu_full).data, status=status.HTTP_201_CREATED)


class MenuListView(generics.ListAPIView):
    # Freemium: свои сгенерированные меню доступны и бесплатным семьям.
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
    # Freemium: свои сгенерированные меню доступны и бесплатным семьям.
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
    """MG_608_V_views: Список меню в карантине (только не истёкшие)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        items = DeletedMenu.objects.filter(
            family=family,
            purge_after__gte=timezone.now(),
        )
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

        # MG_608_V_views: запрет восстановления истёкших записей
        if deleted.purge_after < timezone.now():
            return Response(
                {"detail": "Срок хранения в карантине истёк."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not _can_delete_menu(request.user, family, type("M", (), {"creator_id": deleted.deleted_by_id})()):
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
                        meal_slot=item.get("meal_slot", item["meal_type"]),
                        component_role=item.get("component_role", "other"),
                        is_cheat_meal=item.get("is_cheat_meal", False),
                        day_offset=item["day_offset"],
                    )  # MG_602_V_views: убран is_salad (поле удалено), добавлены meal_slot/component_role/is_cheat_meal
                except Recipe.DoesNotExist:
                    pass
            deleted.delete()

        menu_full = Menu.objects.prefetch_related("items__recipe", "items__member__user").get(id=menu.id)
        return Response(MenuDetailSerializer(menu_full).data, status=status.HTTP_201_CREATED)


class MenuPurgeView(APIView):
    """MG_608_V_views: окончательное удаление одной записи из карантина."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, deleted_id):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            deleted = DeletedMenu.objects.get(id=deleted_id, family=family)
        except DeletedMenu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not _can_delete_menu(request.user, family, type("M", (), {"creator_id": deleted.deleted_by_id})()):
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)

        deleted.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MenuPurgeAllView(APIView):
    """MG_608_V_views: окончательное удаление всех записей карантина семьи."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # Только admin или head могут чистить всё
        is_admin = getattr(request.user, "user_type", "") == "admin"
        is_head = FamilyMember.objects.filter(family=family, user=request.user, role=FamilyMember.Role.HEAD).exists()
        if not (is_admin or is_head):
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)

        cnt, _ = DeletedMenu.objects.filter(family=family).delete()
        return Response({"deleted": cnt}, status=status.HTTP_200_OK)


class MenuItemSwapView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

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

        # MG-402: запрещаем swap на рецепт другой food_group
        original_fg = getattr(item.recipe, "food_group", None)
        new_fg = getattr(recipe, "food_group", None)
        if original_fg and new_fg and original_fg != new_fg:
            return Response(
                {"detail": f"Рецепт другой группы ({new_fg}), ожидается {original_fg}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        return Response(
            {
                "allergen_warning": allergen_warning,
                "allergens_found": found_allergens,
                "calorie_warning": calorie_warning,
                "recipe_calories": cal,
            },
            status=status.HTTP_200_OK,
        )


class MenuArchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

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
