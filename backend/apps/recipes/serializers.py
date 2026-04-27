from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Recipe, RecipeAuthor

User = get_user_model()


CLASSIFICATION_FIELDS = (
    "food_group",
    "suitable_for",
    "protein_type",
    "grain_type",
    "is_fatty_fish",
    "is_red_meat",
)


class RecipeListSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "title",
            "cook_time",
            "servings",
            "categories",
            "image_url",
            "nutrition",
            "country",
            "is_custom",
            "author_name",
            "created_at",
        ) + CLASSIFICATION_FIELDS


class RecipeDetailSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "legacy_id",
            "title",
            "cook_time",
            "servings",
            "ingredients",
            "steps",
            "nutrition",
            "categories",
            "image_url",
            "video_url",
            "source_url",
            "country",
            "is_custom",
            "is_published",
            "author_name",
            "created_at",
            "updated_at",
        ) + CLASSIFICATION_FIELDS


class RecipeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = (
            "title",
            "cook_time",
            "servings",
            "ingredients",
            "steps",
            "nutrition",
            "categories",
            "image_url",
            "video_url",
            "country",
        ) + CLASSIFICATION_FIELDS

    def validate_ingredients(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается массив.")
        for item in value:
            if not isinstance(item, dict) or "name" not in item:
                raise serializers.ValidationError("Каждый ингредиент должен содержать поле name.")
        return value

    def validate_steps(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается массив.")
        for item in value:
            if not isinstance(item, dict) or "text" not in item:
                raise serializers.ValidationError("Каждый шаг должен содержать поле text.")
        return value

    def validate_suitable_for(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается массив.")
        allowed = {"breakfast", "lunch", "dinner", "snack"}
        for item in value:
            if item not in allowed:
                raise serializers.ValidationError(
                    f"Недопустимое значение '{item}'. Допустимы: {sorted(allowed)}."
                )
        return value

    def validate(self, attrs):
        # на partial_update в attrs может не быть полей — берём из instance
        def get_val(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        food_group = get_val("food_group")
        if food_group == Recipe.FoodGroup.GRAIN and not get_val("grain_type"):
            raise serializers.ValidationError(
                {"grain_type": "Обязательно при food_group=grain (whole / refined)."}
            )
        if food_group == Recipe.FoodGroup.PROTEIN and not get_val("protein_type"):
            raise serializers.ValidationError(
                {"protein_type": "Обязательно при food_group=protein (animal / plant / mixed)."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        validated_data["is_custom"] = True
        return super().create(validated_data)


class RecipeAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeAuthor
        fields = ("id", "status", "motivation_text", "applied_at", "approved_at", "recipes_count")
        read_only_fields = ("id", "status", "applied_at", "approved_at", "recipes_count")
