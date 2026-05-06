from datetime import date

from rest_framework import serializers

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
    meal_plan_type = serializers.ChoiceField(choices=['3', '5'], default='3', required=False)


class MenuItemSerializer(serializers.ModelSerializer):
    recipe = RecipeListSerializer(read_only=True)
    member_name = serializers.CharField(source="member.user.name", read_only=True, default=None)

    class Meta:
        model = MenuItem
        fields = ("id", "day_offset", "meal_type", "meal_slot", "component_role", "recipe", "member_name", "quantity")


class MenuItemSwapSerializer(serializers.Serializer):
    recipe_id = serializers.IntegerField()


class MenuListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ("id", "start_date", "end_date", "period_days", "status", "generated_at")


class MenuDetailSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

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
