from rest_framework import serializers

from .models import FridgeItem, Product, ProductCategory


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ("id", "slug", "name_ru", "name_en", "icon", "color", "sort_order")


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField(read_only=True)  # legacy string
    category_id = serializers.PrimaryKeyRelatedField(
        source="category_fk",
        queryset=ProductCategory.objects.all(),
        allow_null=True,
        required=False,
    )
    category_slug = serializers.CharField(source="category_fk.slug", read_only=True, default=None)
    category_name = serializers.CharField(source="category_fk.name_ru", read_only=True, default=None)
    category_icon = serializers.CharField(source="category_fk.icon", read_only=True, default=None)
    category_color = serializers.CharField(source="category_fk.color", read_only=True, default=None)

    class Meta:
        model = Product
        fields = (
            "id", "name",
            "category",
            "category_id",
            "category_slug",
            "category_name",
            "category_icon",
            "category_color",
            "default_unit",
            "calories_per_100g", "nutrition",
            "barcode", "image_url",
            "is_seed",
        )


class FridgeItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    product_category = serializers.CharField(source="product.category", read_only=True, default=None)
    product_category_id = serializers.IntegerField(source="product.category_fk_id", read_only=True, default=None)
    product_category_slug = serializers.CharField(source="product.category_fk.slug", read_only=True, default=None)
    product_category_name = serializers.CharField(source="product.category_fk.name_ru", read_only=True, default=None)
    product_category_icon = serializers.CharField(source="product.category_fk.icon", read_only=True, default=None)
    product_category_color = serializers.CharField(source="product.category_fk.color", read_only=True, default=None)
    product_image_url = serializers.CharField(source="product.image_url", read_only=True, default=None)

    class Meta:
        model = FridgeItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_category",
            "product_category_id",
            "product_category_slug",
            "product_category_name",
            "product_category_icon",
            "product_category_color",
            "product_image_url",
            "name",
            "quantity",
            "unit",
            "expiry_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip()


class FridgeItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FridgeItem
        fields = ("product", "name", "quantity", "unit", "expiry_date")

    def create(self, validated_data):
        family = self.context["family"]
        user = self.context["request"].user
        return FridgeItem.objects.create(
            **validated_data,
            family=family,
            added_by_id=user.id,
        )


class BarcodeLookupSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=64)


class FridgeHistoryItemSerializer(serializers.Serializer):
    """Aggregated suggestion: name + last-used metadata (no DB model)."""
    name = serializers.CharField()
    product_id = serializers.IntegerField(allow_null=True)
    category_id = serializers.IntegerField(allow_null=True)
    category_slug = serializers.CharField(allow_null=True, allow_blank=True)
    category_name = serializers.CharField(allow_null=True, allow_blank=True)
    category_icon = serializers.CharField(allow_null=True, allow_blank=True)
    category_color = serializers.CharField(allow_null=True, allow_blank=True)
    default_unit = serializers.CharField(allow_blank=True)
    image_url = serializers.CharField(allow_null=True, allow_blank=True)
    times_used = serializers.IntegerField()
    last_used = serializers.DateTimeField(allow_null=True)
