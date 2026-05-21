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
            "id",
            "name",
            "category",
            "category_id",
            "category_slug",
            "category_name",
            "category_icon",
            "category_color",
            "default_unit",
            "calories_per_100g",
            "nutrition",
            "barcode",
            "image_url",
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
    # MENUGEN_ADD_PRODUCT: optional fields from AI photo recognition.
    # When present we create/find a Product so the item carries a category
    # (fixes 'Прочее' grouping) and KBJU (fixes empty nutrition card).
    category_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    calories_per_100g = serializers.FloatField(write_only=True, required=False, allow_null=True)
    nutrition = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = FridgeItem
        fields = (
            "product",
            "name",
            "quantity",
            "unit",
            "expiry_date",
            "category_slug",
            "calories_per_100g",
            "nutrition",
        )

    def _resolve_product(self, name, category_slug, calories, nutrition):
        """Find/create a Product to attach KBJU + category to the item.

        Source priority for KBJU (per product decision):
          1) existing local Product (by case-insensitive name) that already
             has nutrition -> reuse it;
          2) otherwise write the label-extracted KBJU onto the product.
        Returns a Product or None (None when nothing to attach).
        """
        from .models import Product, ProductCategory

        name = (name or "").strip()
        if not name:
            return None

        cat = None
        slug = (category_slug or "").strip()
        if slug:
            cat = ProductCategory.objects.filter(is_active=True, slug=slug).first()

        nutrition = nutrition if isinstance(nutrition, dict) else {}
        has_label_kbju = bool(nutrition) or calories is not None

        # 1) reuse an existing product that already carries nutrition
        existing = Product.objects.filter(name__iexact=name).order_by("id").first()
        if existing is not None:
            updates = []
            if cat is not None and existing.category_fk_id != cat.id:
                existing.category_fk = cat
                updates.append("category_fk")
            # fill KBJU only if product lacks it and we have it from the label
            if not existing.nutrition and nutrition:
                existing.nutrition = nutrition
                updates.append("nutrition")
            if existing.calories_per_100g is None and calories is not None:
                existing.calories_per_100g = calories
                updates.append("calories_per_100g")
            if updates:
                existing.save(update_fields=updates)
            return existing

        # 2) nothing to attach? skip product creation
        if cat is None and not has_label_kbju:
            return None

        return Product.objects.create(
            name=name[:255],
            category_fk=cat,
            calories_per_100g=calories,
            nutrition=nutrition,
        )

    def create(self, validated_data):
        family = self.context["family"]
        user = self.context["request"].user
        category_slug = validated_data.pop("category_slug", "")
        calories = validated_data.pop("calories_per_100g", None)
        nutrition = validated_data.pop("nutrition", None)

        # If the client did not pass an explicit product FK, try to build one
        # from the recognized category/KBJU so the item is categorized + has
        # nutrition. Manual adds without any of these keep product=None.
        if not validated_data.get("product"):
            product = self._resolve_product(validated_data.get("name"), category_slug, calories, nutrition)
            if product is not None:
                validated_data["product"] = product

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


# >>> MENUGEN_VISION_BEGIN (managed block — do not edit between markers)


# ─── Photo recognition (OCR + LLM) ──────────────────────────────────────────
class RecognizePhotoRequestSerializer(serializers.Serializer):
    """Accepts either a multipart file (`image`) or a base64 string (`image_b64`)."""

    image = serializers.ImageField(required=False, write_only=True)
    image_b64 = serializers.CharField(required=False, write_only=True, allow_blank=True)
    mode = serializers.ChoiceField(choices=("single", "multi"), default="single")

    def validate(self, attrs):
        if not attrs.get("image") and not attrs.get("image_b64"):
            raise serializers.ValidationError("Передайте фото: поле 'image' (файл) или 'image_b64'.")
        return attrs


class RecognizedProductSerializer(serializers.Serializer):
    """One recognized product, enriched with matched ProductCategory if found."""

    name = serializers.CharField()
    category = serializers.CharField(allow_blank=True)
    quantity = serializers.CharField(allow_null=True, required=False)
    confidence = serializers.FloatField()
    calories_per_100g = serializers.FloatField(allow_null=True, required=False)  # MENUGEN_ADD_PRODUCT
    nutrition = serializers.DictField(required=False)
    category_id = serializers.IntegerField(allow_null=True, required=False)
    category_slug = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    category_name = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    category_icon = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    category_color = serializers.CharField(allow_null=True, allow_blank=True, required=False)


# <<< MENUGEN_VISION_END
