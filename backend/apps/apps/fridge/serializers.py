from rest_framework import serializers

from .models import FridgeItem, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "category", "default_unit", "calories_per_100g", "nutrition", "barcode")


class FridgeItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    product_category = serializers.CharField(source="product.category", read_only=True, default=None)

    class Meta:
        model = FridgeItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_category",
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
