"""MG_CONSTRUCTOR: сериализаторы ручного конструктора меню.

Приём/отдача всей структуры (меню → приёмы → блюда) одним объектом. На запись
приёмы/блюда передаются вложенно и полностью пересоздаются (билдер шлёт весь
состав при сохранении).
"""

from rest_framework import serializers

from apps.fridge.models import Product
from apps.recipes.models import Recipe

from .models import ConstructedMeal, ConstructedMealItem, ConstructedMenu


class _RecipeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "title", "image_url")


class _ProductMiniSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category_fk.name_ru", read_only=True, default=None)

    class Meta:
        model = Product
        fields = ("id", "name", "image_url", "category_name")


class ConstructedMealItemSerializer(serializers.ModelSerializer):
    # Позиция приёма: рецепт ИЛИ продукт (с порцией в граммах). MG_PRODDISH.
    recipe = _RecipeMiniSerializer(read_only=True)
    recipe_id = serializers.PrimaryKeyRelatedField(
        queryset=Recipe.objects.all(), source="recipe", write_only=True, required=False, allow_null=True
    )
    product = _ProductMiniSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True, required=False, allow_null=True
    )
    # MG_PRODFAMILY: см. validate_product_id — queryset здесь общий (он строится
    # один раз на класс), а видимость проверяется по текущему пользователю.
    # КБЖУ продукта-блюда на заданную порцию (для рецепта — null, берётся из рецепта).
    nutrition = serializers.SerializerMethodField()

    class Meta:
        model = ConstructedMealItem
        fields = ("id", "recipe", "recipe_id", "product", "product_id", "grams", "quantity", "nutrition")

    def get_nutrition(self, obj):
        if obj.product_id and obj.grams:
            return obj.product.nutrition_for_grams(obj.grams)
        return None

    def validate_product_id(self, product):
        """MG_PRODFAMILY: продукт — из каталога или из своей семьи.

        Специалист строит меню из общего справочника; продукт чужой семьи
        по произвольному id сюда попасть не должен.
        """
        if product is None:
            return product
        from apps.fridge.visibility import visible_products_q

        user = self.context["request"].user
        if not Product.objects.filter(visible_products_q(user)).filter(id=product.id).exists():
            raise serializers.ValidationError("Продукт недоступен.")
        return product

    def validate(self, attrs):
        # Ровно один источник: рецепт ИЛИ продукт.
        recipe = attrs.get("recipe")
        product = attrs.get("product")
        if bool(recipe) == bool(product):
            raise serializers.ValidationError("Укажите либо рецепт, либо продукт (ровно одно).")
        if product and not attrs.get("grams"):
            raise serializers.ValidationError("Для продукта-блюда укажите порцию в граммах.")
        return attrs


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

    def validate_client_family(self, family):
        """Привязать меню можно только к своей семье-клиенту.

        Список семей в конструкторе уже отфильтрован, но фильтр списка чужой
        client_family не остановит: без этой проверки специалист мог отправить
        произвольный id и привязать меню к любой семье. Пустой client_family —
        это меню-шаблон, не привязанное ни к кому, и он разрешён.
        """
        if family is None:
            return family
        from .constructor_views import allowed_family_ids

        user = self.context["request"].user
        if family.id not in allowed_family_ids(user):
            raise serializers.ValidationError("Эта семья не в списке ваших клиентов.")
        return family

    def _write_meals(self, menu, meals_data):
        menu.meals.all().delete()
        for m in meals_data:
            items = m.pop("items", [])
            meal = ConstructedMeal.objects.create(menu=menu, **m)
            ConstructedMealItem.objects.bulk_create(
                [
                    ConstructedMealItem(
                        meal=meal,
                        recipe=it.get("recipe"),
                        product=it.get("product"),
                        grams=it.get("grams"),
                        quantity=it.get("quantity", 1),
                    )
                    for it in items
                ]
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
