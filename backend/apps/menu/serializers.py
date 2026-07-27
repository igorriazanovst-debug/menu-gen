# MG_505_V_serializers
from datetime import date

from rest_framework import serializers

from apps.family.models import FamilyMember
from apps.recipes.serializers import RecipeListSerializer

from .models import Menu, MenuItem, ShoppingItem, ShoppingList


class GenerateMenuSerializer(serializers.Serializer):
    period_days = serializers.IntegerField(min_value=1, max_value=30, default=7)
    start_date = serializers.DateField(default=date.today)
    country = serializers.CharField(required=False, allow_blank=True)
    max_cook_time = serializers.IntegerField(required=False, min_value=1)
    member_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    calorie_min = serializers.IntegerField(required=False, min_value=0)
    calorie_max = serializers.IntegerField(required=False, min_value=0)
    meal_plan_type = serializers.ChoiceField(choices=["3", "5"], default="3", required=False)
    with_soup = serializers.BooleanField(default=True, required=False)  # MG_610_V_generator
    strategy = serializers.ChoiceField(choices=["1", "2", "3"], default="1", required=False)  # MG_STRAT
    # MG_605A_V_serializers: mode мульти-член (per_member | family)
    mode = serializers.ChoiceField(choices=["per_member", "family"], default="family", required=False)
    # MG_607_V_serializers: мульти-выбор стран + per-request override allergens/disliked
    countries = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )
    exclude_allergens = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )
    exclude_disliked = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )


class _ProductDishMiniSerializer(serializers.Serializer):
    """MG_PRODDISH: краткая карточка продукта-блюда (для веба)."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    image_url = serializers.CharField(allow_null=True, required=False)
    category_name = serializers.CharField(source="category_fk.name_ru", allow_null=True, required=False, default=None)


class MenuItemSerializer(serializers.ModelSerializer):
    # MG_PRODDISH: позиция — рецепт ИЛИ продукт. Для обратной совместимости
    # клиентов (в т.ч. мобильного) продукт отдаётся ещё и как «синтетический»
    # recipe-объект (title/nutrition/image), а сырые product/grams — доп. полями.
    recipe = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    member_name = serializers.CharField(source="member.user.name", read_only=True, default=None)
    member = serializers.IntegerField(source="member_id", read_only=True, default=None)  # MG_FAMILYGEN

    class Meta:
        model = MenuItem
        fields = (
            "id",
            "day_offset",
            "meal_type",
            "meal_slot",
            "component_role",
            "recipe",
            "product",
            "grams",
            "member",
            "member_name",
            "quantity",
            "is_cheat_meal",
        )

    def get_recipe(self, obj):
        if obj.recipe_id:
            return RecipeListSerializer(obj.recipe, context=self.context).data
        if obj.product_id:
            return self._synthetic_recipe(obj)
        return None

    def get_product(self, obj):
        if not obj.product_id:
            return None
        return _ProductDishMiniSerializer(obj.product).data

    def _synthetic_recipe(self, obj):
        """Продукт-блюдо в форме recipe-объекта — чтобы старые клиенты его рисовали."""
        p = obj.product
        n = p.nutrition_for_grams(obj.grams)

        def _nv(v, unit):
            return {"value": str(v), "unit": unit} if v is not None else None

        nutrition = {
            k: v
            for k, v in {
                "calories": _nv(n["calories"], "ккал"),
                "proteins": _nv(n["proteins"], "г"),
                "fats": _nv(n["fats"], "г"),
                "carbs": _nv(n["carbs"], "г"),
            }.items()
            if v is not None
        }
        return {
            "id": None,
            "title": p.name,
            "image_url": p.image_url or None,
            "nutrition": nutrition,
            "categories": [p.category_fk.name_ru] if p.category_fk_id else [],
            "is_custom": True,
            "is_product": True,  # маркер, что это продукт-блюдо
        }


class MenuItemSwapSerializer(serializers.Serializer):
    # Замена позиции: рецепт ИЛИ продукт (с порцией в граммах). MG_PRODDISH.
    recipe_id = serializers.IntegerField(required=False)
    product_id = serializers.IntegerField(required=False)
    grams = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        if bool(attrs.get("recipe_id")) == bool(attrs.get("product_id")):
            raise serializers.ValidationError("Укажите либо recipe_id, либо product_id (ровно одно).")
        if attrs.get("product_id") and not attrs.get("grams"):
            raise serializers.ValidationError("Для продукта укажите порцию в граммах (grams).")
        return attrs


class MenuListSerializer(serializers.ModelSerializer):

    # MG_B09: expose creator display name (creator_id -> User.name)
    creator_name = serializers.SerializerMethodField()

    def get_creator_name(self, obj):
        from django.contrib.auth import get_user_model

        U = get_user_model()
        cid = getattr(obj, "creator_id", None)
        if not cid:
            return ""
        u = U.objects.filter(pk=cid).only("name").first()
        return (getattr(u, "name", "") or "") if u else ""

    class Meta:
        model = Menu
        fields = ("id", "start_date", "end_date", "period_days", "status", "generated_at", "creator_name")  # MG_B09


class MenuDetailSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    # MG_FAMILYGEN: кто смотрит (для фильтра «свои приёмы» и окна главы семьи).
    my_member_id = serializers.SerializerMethodField()
    is_head = serializers.SerializerMethodField()

    def _my_member(self, obj):
        req = self.context.get("request")
        user = getattr(req, "user", None) if req else None
        if not user or not getattr(user, "is_authenticated", False):
            return None
        return FamilyMember.objects.filter(family=obj.family, user=user).only("id", "role").first()

    def get_my_member_id(self, obj):
        m = self._my_member(obj)
        return m.id if m else None

    def get_is_head(self, obj):
        m = self._my_member(obj)
        return bool(m and m.role == FamilyMember.Role.HEAD)

    class Meta:
        model = Menu
        fields = (
            "id",
            "start_date",
            "end_date",
            "period_days",
            "status",
            "filters_used",
            "generated_at",
            "updated_at",
            "items",
            "warnings",  # MG_304_V_serializers
            "my_member_id",
            "is_head",
        )


class ShoppingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingItem
        fields = ("id", "name", "quantity", "unit", "category", "is_purchased")


class ShoppingListSerializer(serializers.ModelSerializer):
    items = ShoppingItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShoppingList
        fields = ("id", "items", "created_at")


class DeletedMenuSerializer(serializers.ModelSerializer):
    deleted_by_name = serializers.CharField(source="deleted_by.name", read_only=True, default=None)
    can_purge = serializers.SerializerMethodField()

    class Meta:
        from .models import DeletedMenu

        model = DeletedMenu
        fields = ("id", "menu_id", "data", "deleted_by_name", "deleted_at", "purge_after", "can_purge")

    def get_can_purge(self, obj):
        from django.utils import timezone

        return timezone.now() >= obj.purge_after
