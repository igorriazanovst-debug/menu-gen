# MG_SHOP001_serializers
from rest_framework import serializers

from apps.users.models import User

from .models import (
    PurchaseHistoryEntry,
    ShoppingList,
    ShoppingListAccess,
    ShoppingListItem,
)


class ShoppingListItemSerializer(serializers.ModelSerializer):
    purchased_by_name = serializers.CharField(
        source="purchased_by.name", read_only=True, default=None
    )

    class Meta:
        model = ShoppingListItem
        fields = (
            "id", "product_id", "name", "quantity", "unit", "category",
            "is_purchased", "purchased_by", "purchased_by_name",
            "purchased_at", "sort_order",
        )
        read_only_fields = ("purchased_by", "purchased_by_name", "purchased_at")


class ShoppingListItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingListItem
        fields = ("name", "quantity", "unit", "category", "sort_order")


class ShoppingListAccessSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(
        source="user.name", read_only=True, default=None
    )

    class Meta:
        model = ShoppingListAccess
        fields = (
            "id", "user", "user_email", "user_name",
            "can_read", "can_toggle", "can_export", "granted_at",
        )
        read_only_fields = ("granted_at",)


class GrantAccessSerializer(serializers.Serializer):
    """Grant by user_id (family member) OR email (any app user)."""

    user_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False)
    can_toggle = serializers.BooleanField(default=False)
    can_export = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs.get("user_id") and not attrs.get("email"):
            raise serializers.ValidationError("user_id или email обязателен.")
        return attrs

    def resolve_user(self):
        data = self.validated_data
        if data.get("user_id"):
            try:
                return User.objects.get(id=data["user_id"])
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_id": "Пользователь не найден."})
        try:
            return User.objects.get(email=data["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Пользователь не найден."})


class ShoppingListSerializer(serializers.ModelSerializer):
    items = ShoppingListItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.name", read_only=True, default=None
    )
    items_total = serializers.IntegerField(read_only=True, required=False)
    items_purchased = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ShoppingList
        fields = (
            "id", "name", "source", "menu", "is_archived",
            "created_by", "created_by_name", "created_at", "updated_at",
            "archived_at", "items", "items_total", "items_purchased",
        )
        read_only_fields = ("source", "created_by", "archived_at")


class ShoppingListBriefSerializer(serializers.ModelSerializer):
    items_total = serializers.IntegerField(read_only=True, required=False)
    items_purchased = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ShoppingList
        fields = (
            "id", "name", "source", "is_archived",
            "created_at", "updated_at", "items_total", "items_purchased",
        )


class PurchaseHistoryEntrySerializer(serializers.ModelSerializer):
    purchased_by_name = serializers.CharField(
        source="purchased_by.name", read_only=True, default=None
    )

    class Meta:
        model = PurchaseHistoryEntry
        fields = (
            "id", "name", "quantity", "unit", "category",
            "purchased_by", "purchased_by_name", "purchased_at", "source_list_id",
        )


class CreateListSerializer(serializers.Serializer):
    """Body for POST /shopping/lists/ — covers 1.1/1.2/1.3."""

    name = serializers.CharField(max_length=255)
    source = serializers.ChoiceField(
        choices=ShoppingList.Source.choices, default=ShoppingList.Source.EMPTY
    )
    menu_id = serializers.IntegerField(required=False)
    subtract_fridge = serializers.BooleanField(default=False)
    text = serializers.CharField(required=False, allow_blank=True)
    csv_text = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        src = attrs["source"]
        if src in (ShoppingList.Source.MENU, ShoppingList.Source.FRIDGE) and not attrs.get("menu_id"):
            raise serializers.ValidationError({"menu_id": "Обязателен для source=menu/fridge."})
        if src == ShoppingList.Source.AI_TEXT and not attrs.get("text"):
            raise serializers.ValidationError({"text": "Обязателен для source=ai_text."})
        if src == ShoppingList.Source.CSV and not attrs.get("csv_text"):
            raise serializers.ValidationError({"csv_text": "Обязателен для source=csv."})
        return attrs
