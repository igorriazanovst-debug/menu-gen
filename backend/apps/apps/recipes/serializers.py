from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Recipe, RecipeAuthor

User = get_user_model()


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
        )


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
        )


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
        )

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

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        validated_data["is_custom"] = True
        return super().create(validated_data)


class RecipeAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeAuthor
        fields = ("id", "status", "motivation_text", "applied_at", "approved_at", "recipes_count")
        read_only_fields = ("id", "status", "applied_at", "approved_at", "recipes_count")
