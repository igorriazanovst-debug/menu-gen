# MG_SHOP001_serializers
from rest_framework import serializers

from apps.users.models import User

from .models import PurchaseHistoryEntry, ShoppingList, ShoppingListAccess, ShoppingListItem


class ShoppingListItemSerializer(serializers.ModelSerializer):
    purchased_by_name = serializers.CharField(source="purchased_by.name", read_only=True, default=None)
    # MG_RUBRIC002: expose rubricator category via FK.
    category_slug = serializers.CharField(source="category_fk.slug", read_only=True, default=None)
    category_name = serializers.CharField(source="category_fk.name_ru", read_only=True, default=None)
    # MG_RUBRIC006_read_price: line total = quantity * price_per_unit.
    line_total = serializers.SerializerMethodField()

    def get_line_total(self, obj):
        if obj.price_per_unit is None:
            return None
        qty = obj.quantity if obj.quantity is not None else 1
        return str(obj.price_per_unit * qty)

    class Meta:
        model = ShoppingListItem
        # MG_RUBRIC002_read_fields
        # MG_RUBRIC003_read_legacy
        fields = (
            "id",
            "legacy_product_id",
            "name",
            "quantity",
            "unit",
            "category",
            "category_slug",
            "category_name",
            "price_per_unit",  # MG_RUBRIC006_read_fields_price
            "line_total",
            "is_purchased",
            "purchased_by",
            "purchased_by_name",
            "purchased_at",
            "sort_order",
        )
        read_only_fields = ("purchased_by", "purchased_by_name", "purchased_at")


class ShoppingListItemWriteSerializer(serializers.ModelSerializer):
    # MG_RUBRIC002: optional rubricator links.
    category_slug = serializers.CharField(required=False, allow_blank=True, write_only=True)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    # MG_RUBRIC006_write_price
    price_per_unit = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = ShoppingListItem
        fields = (
            "name",
            "quantity",
            "unit",
            "category",
            "category_slug",
            "product_id",
            "price_per_unit",
            "sort_order",
        )


class ShoppingListAccessSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True, default=None)

    class Meta:
        model = ShoppingListAccess
        fields = (
            "id",
            "user",
            "user_email",
            "user_name",
            "can_read",
            "can_toggle",
            "can_export",
            "granted_at",
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
    created_by_name = serializers.CharField(source="created_by.name", read_only=True, default=None)
    items_total = serializers.IntegerField(read_only=True, required=False)
    items_purchased = serializers.IntegerField(read_only=True, required=False)
    # MG_RUBRIC006_list_total
    currency = serializers.CharField(source="family.currency", read_only=True, default="RUB")
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, obj):
        from decimal import Decimal

        total = Decimal(0)
        any_price = False
        for it in obj.items.all():
            if it.price_per_unit is None:
                continue
            any_price = True
            qty = it.quantity if it.quantity is not None else 1
            total += it.price_per_unit * qty
        return str(total) if any_price else None

    class Meta:
        model = ShoppingList
        fields = (
            "id",
            "name",
            "source",
            "menu",
            "is_archived",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "archived_at",
            "items",
            "items_total",
            "items_purchased",
            "currency",  # MG_RUBRIC006_detail_fields
            "total_price",
        )
        read_only_fields = ("source", "created_by", "archived_at")


class ShoppingListBriefSerializer(serializers.ModelSerializer):
    items_total = serializers.IntegerField(read_only=True, required=False)
    items_purchased = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ShoppingList
        fields = (
            "id",
            "name",
            "source",
            "is_archived",
            "created_at",
            "updated_at",
            "items_total",
            "items_purchased",
        )


class PurchaseHistoryEntrySerializer(serializers.ModelSerializer):
    purchased_by_name = serializers.CharField(source="purchased_by.name", read_only=True, default=None)

    class Meta:
        model = PurchaseHistoryEntry
        # MG_RUBRIC006_history_price
        fields = (
            "id",
            "name",
            "quantity",
            "unit",
            "category",
            "price_per_unit",
            "purchased_by",
            "purchased_by_name",
            "purchased_at",
            "source_list_id",
        )


class CreateListSerializer(serializers.Serializer):
    """Body for POST /shopping/lists/ — covers 1.1/1.2/1.3."""

    name = serializers.CharField(max_length=255)
    source = serializers.ChoiceField(choices=ShoppingList.Source.choices, default=ShoppingList.Source.EMPTY)
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
