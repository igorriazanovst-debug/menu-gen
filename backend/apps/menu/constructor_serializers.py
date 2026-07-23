"""MG_CONSTRUCTOR: сериализаторы ручного конструктора меню.

Приём/отдача всей структуры (меню → приёмы → блюда) одним объектом. На запись
приёмы/блюда передаются вложенно и полностью пересоздаются (билдер шлёт весь
состав при сохранении).
"""

from rest_framework import serializers

from apps.recipes.models import Recipe

from .models import ConstructedMeal, ConstructedMealItem, ConstructedMenu


class _RecipeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "title", "image_url")


class ConstructedMealItemSerializer(serializers.ModelSerializer):
    # на запись — id рецепта, на чтение — краткая карточка
    recipe = _RecipeMiniSerializer(read_only=True)
    recipe_id = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), source="recipe", write_only=True)

    class Meta:
        model = ConstructedMealItem
        fields = ("id", "recipe", "recipe_id", "quantity")


class ConstructedMealSerializer(serializers.ModelSerializer):
    items = ConstructedMealItemSerializer(many=True)

    class Meta:
        model = ConstructedMeal
        fields = (
            "id",
            "day_index",
            "order",
            "name",
            "target_calories",
            "target_protein",
            "target_fat",
            "target_carbs",
            "items",
        )


class ConstructedMenuSerializer(serializers.ModelSerializer):
    meals = ConstructedMealSerializer(many=True)
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)

    class Meta:
        model = ConstructedMenu
        fields = (
            "id",
            "name",
            "author_name",
            "client_family",
            "days",
            "status",
            "meals",
            "created_at",
            "updated_at",
        )

    def _write_meals(self, menu, meals_data):
        menu.meals.all().delete()
        for m in meals_data:
            items = m.pop("items", [])
            meal = ConstructedMeal.objects.create(menu=menu, **m)
            ConstructedMealItem.objects.bulk_create(
                [ConstructedMealItem(meal=meal, recipe=it["recipe"], quantity=it.get("quantity", 1)) for it in items]
            )

    def create(self, validated_data):
        meals_data = validated_data.pop("meals", [])
        menu = ConstructedMenu.objects.create(author=self.context["request"].user, **validated_data)
        self._write_meals(menu, meals_data)
        return menu

    def update(self, instance, validated_data):
        meals_data = validated_data.pop("meals", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if meals_data is not None:
            self._write_meals(instance, meals_data)
        return instance


class ConstructedMenuListSerializer(serializers.ModelSerializer):
    """Компактный список (без вложенного состава)."""

    author_name = serializers.CharField(source="author.name", read_only=True, default=None)
    client_family_name = serializers.CharField(source="client_family.name", read_only=True, default=None)
    meals_count = serializers.IntegerField(source="meals.count", read_only=True)

    class Meta:
        model = ConstructedMenu
        fields = (
            "id",
            "name",
            "author_name",
            "client_family",
            "client_family_name",
            "days",
            "status",
            "meals_count",
            "created_at",
            "updated_at",
        )
