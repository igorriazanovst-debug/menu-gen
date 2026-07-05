from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Recipe, RecipeAuthor, RecipeFavorite

User = get_user_model()


# KBJU_DISPLAY: БД хранит nutrition как ПЛОСКИЙ dict чисел на 100 г:
#   {"calories": 83.0, "proteins": 2.7, "fats": 5.9, "carbs": 1.0, "sugars": 0.4}
# Весь фронт (web + mobile) исторически ждёт ВЛОЖЕННЫЙ формат {value, unit}.
# Нормализуем на чтении в сериализаторе, БД и фронт не трогаем.
_NUTRITION_UNITS = {
    "calories": "ккал",
    "proteins": "г",
    "fats": "г",
    "carbs": "г",
    "sugars": "г",
    "fiber": "г",
    "weight": "г",
}


def normalize_nutrition(raw):
    """flat {key: number} -> {key: {"value": "X", "unit": "..."}};
    уже вложенный формат оставляем как есть; None -> {}."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            # уже {value, unit} — оставляем
            out[key] = val
            continue
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        # 83.0 -> "83", 5.9 -> "5.9"
        text = str(int(num)) if num == int(num) else str(round(num, 1))
        out[key] = {"value": text, "unit": _NUTRITION_UNITS.get(key, "")}
    return out


class _NutritionNormalizeMixin(serializers.Serializer):
    """Подменяет поле nutrition на нормализованное представление."""

    nutrition = serializers.SerializerMethodField()

    def get_nutrition(self, obj):
        return normalize_nutrition(getattr(obj, "nutrition", None))


CLASSIFICATION_FIELDS = (
    "food_group",
    "suitable_for",
    "protein_type",
    "grain_type",
    "is_fatty_fish",
    "is_red_meat",
)

MG501_FIELDS = (
    "cooking_method",
    "has_added_sugar",
    "oil_tsp",
    "serving_size_label",
)

# Надёжные числовые поля КБЖУ (в обход рассогласованного nutrition JSON).
# Используются ручным добавлением рецепта в дневник: per-100g для граммовки,
# per-порционные — для fallback на порции. portion_g — вес одной порции.
NUTRITION_NUMERIC_FIELDS = (
    "portion_g",
    "kcal",
    "proteins",
    "fats",
    "carbs",
    "kcal_per_100g",
    "proteins_per_100g",
    "fats_per_100g",
    "carbs_per_100g",
)


class _FavoriteStateMixin(serializers.Serializer):
    """Adds ``is_favorite`` / ``is_disliked`` derived from the current user."""

    is_favorite = serializers.SerializerMethodField()
    is_disliked = serializers.SerializerMethodField()

    def _get_fav(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        cache = self.context.get("favorites_cache")
        if cache is None:
            return RecipeFavorite.objects.filter(user=request.user, recipe=obj).first()
        return cache.get(obj.id)

    def get_is_favorite(self, obj):
        f = self._get_fav(obj)
        return bool(f and f.is_favorite)

    def get_is_disliked(self, obj):
        f = self._get_fav(obj)
        return bool(f and not f.is_favorite)


# MG_FIX_IMAGE_URL_ABSOLUTE / MG_PUBLIC_BACKEND_URL
import os as _mg_os  # noqa: E402


def _mg_public_backend_url():
    return (_mg_os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")


class _AbsoluteImageUrlMixin:
    """image_url -> absolute URL.
    Priority:
      1) если url уже абсолютный (http/https) — отдаём как есть.
      2) если задан env BACKEND_PUBLIC_URL — префикс оттуда (фиксирован, не зависит
         от Host текущего запроса). Это решает кейс когда фронт ходит на один порт,
         а статика должна грузиться с публичного backend на другом.
      3) иначе fall back на request.build_absolute_uri.
    """

    def get_image_url(self, obj):
        url = obj.image_url
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        public = _mg_public_backend_url()
        if public and url.startswith("/"):
            return public + url
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url


class RecipeListSerializer(
    _NutritionNormalizeMixin, _FavoriteStateMixin, _AbsoluteImageUrlMixin, serializers.ModelSerializer
):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()  # MG_FIX_IMAGE_URL_ABSOLUTE
    fridge_match_count = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            (
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
                "is_favorite",
                "is_disliked",
                "fridge_match_count",
                "allergens",  # MG_ALLERGEN14
            )
            + CLASSIFICATION_FIELDS
            + MG501_FIELDS
            + NUTRITION_NUMERIC_FIELDS
        )

    def get_fridge_match_count(self, obj):
        scores = self.context.get("fridge_scores")
        if not scores:
            return None
        return scores.get(obj.id, 0)


class RecipeDetailSerializer(
    _NutritionNormalizeMixin, _FavoriteStateMixin, _AbsoluteImageUrlMixin, serializers.ModelSerializer
):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()  # MG_FIX_IMAGE_URL_ABSOLUTE

    class Meta:
        model = Recipe
        fields = (
            (
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
                "is_favorite",
                "is_disliked",
                "allergens",  # MG_ALLERGEN14
            )
            + CLASSIFICATION_FIELDS
            + MG501_FIELDS
            + NUTRITION_NUMERIC_FIELDS
        )


class RecipeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = (
            (
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
            + CLASSIFICATION_FIELDS
            + MG501_FIELDS
            + NUTRITION_NUMERIC_FIELDS
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

    def validate_suitable_for(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается массив.")
        allowed = {"breakfast", "lunch", "dinner", "snack"}
        for item in value:
            if item not in allowed:
                raise serializers.ValidationError(f"Недопустимое значение '{item}'. Допустимы: {sorted(allowed)}.")
        return value

    def validate(self, attrs):
        def get_val(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        food_group = get_val("food_group")
        if food_group == Recipe.FoodGroup.GRAIN and not get_val("grain_type"):
            raise serializers.ValidationError({"grain_type": "Обязательно при food_group=grain (whole / refined)."})
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


class RecipeFavoriteWriteSerializer(serializers.Serializer):
    """Body для POST /recipes/{id}/favorite/."""

    is_favorite = serializers.BooleanField()
