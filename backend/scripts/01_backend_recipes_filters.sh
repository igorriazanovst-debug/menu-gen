#!/usr/bin/env bash
# Backend patch: RecipeFavorite + extended filters + ingredient/fridge match
# Idempotent: safe to re-run.
set -eu

ROOT="/opt/menugen"
cd "$ROOT"

echo "=== [1/8] backup current files ==="
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/recipes_filters_${TS}"
mkdir -p "$BAK"
cp backend/apps/recipes/models.py       "$BAK/"
cp backend/apps/recipes/filters.py      "$BAK/"
cp backend/apps/recipes/views.py        "$BAK/"
cp backend/apps/recipes/urls.py         "$BAK/"
cp backend/apps/recipes/serializers.py  "$BAK/"
cp backend/apps/recipes/admin.py        "$BAK/"
echo "backup → $BAK"

echo
echo "=== [2/8] write apps/recipes/models.py (add RecipeFavorite) ==="
cat > backend/apps/recipes/models.py <<'PYEOF'
from django.contrib.postgres.indexes import GinIndex
from django.db import models

from apps.users.models import User


class Recipe(models.Model):
    legacy_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    cook_time = models.CharField(max_length=64, null=True, blank=True)
    servings = models.PositiveSmallIntegerField(null=True, blank=True)
    servings_normalized = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Нормализованное число порций (MG-104d-5)"
    )
    ingredients = models.JSONField(default=list)
    steps = models.JSONField(default=list)
    nutrition = models.JSONField(default=dict)
    categories = models.JSONField(default=list)
    image_url = models.URLField(null=True, blank=True, max_length=1024)
    video_url = models.URLField(null=True, blank=True, max_length=1024)
    source_url = models.URLField(null=True, blank=True, max_length=1024)
    country = models.CharField(max_length=100, null=True, blank=True)
    is_custom = models.BooleanField(default=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="recipes")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class FoodGroup(models.TextChoices):
        GRAIN = "grain", "Зерновые"
        PROTEIN = "protein", "Белки"
        VEGETABLE = "vegetable", "Овощи"
        FRUIT = "fruit", "Фрукты"
        DAIRY = "dairy", "Молочные"
        OIL = "oil", "Масла/жиры"
        OTHER = "other", "Прочее"

    class ProteinType(models.TextChoices):
        ANIMAL = "animal", "Животный"
        PLANT = "plant", "Растительный"
        MIXED = "mixed", "Смешанный"

    class GrainType(models.TextChoices):
        WHOLE = "whole", "Цельнозерновые"
        REFINED = "refined", "Рафинированные"

    class CookingMethod(models.TextChoices):  # MG_501_V_model
        BOILED = "boiled", "Варёное"
        BAKED = "baked", "Запечённое"
        FRIED = "fried", "Жареное"
        GRILLED = "grilled", "Гриль"
        RAW = "raw", "Сырое"
        STEWED = "stewed", "Тушёное"
        STEAMED = "steamed", "На пару"

    food_group = models.CharField(max_length=16, choices=FoodGroup.choices, null=True, blank=True)
    suitable_for = models.JSONField(default=list, blank=True)
    povar_raw = models.JSONField(blank=True, null=True)
    protein_type = models.CharField(max_length=8, choices=ProteinType.choices, null=True, blank=True)
    grain_type = models.CharField(max_length=8, choices=GrainType.choices, null=True, blank=True)
    is_fatty_fish = models.BooleanField(default=False)
    is_red_meat = models.BooleanField(default=False)
    kcal = models.DecimalField(
        max_digits=7, decimal_places=1, null=True, blank=True, help_text="Калорийность на 1 порцию, ккал (MG-104d-4)."
    )
    proteins = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, help_text="Белки на 1 порцию, г."
    )
    fats = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Жиры на 1 порцию, г.")
    carbs = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, help_text="Углеводы на 1 порцию, г."
    )
    cooking_method = models.CharField(
        max_length=16,
        choices=CookingMethod.choices,
        null=True,
        blank=True,
        help_text="Метод приготовления (MG-501).",
    )
    has_added_sugar = models.BooleanField(default=False, help_text="Содержит добавленный сахар (MG-501).")
    oil_tsp = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Расход масла в чайных ложках (MG-501).",
    )
    serving_size_label = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text='Подпись размера порции, напр. "1 тарелка / 200 г" (MG-501).',
    )

    class Meta:
        db_table = "recipes"
        indexes = [
            models.Index(fields=["legacy_id"]),
            models.Index(fields=["country"]),
            models.Index(fields=["author_id"]),
            models.Index(fields=["is_custom"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["food_group"]),
            models.Index(fields=["protein_type"]),
            models.Index(fields=["grain_type"]),
            models.Index(fields=["is_fatty_fish"]),
            models.Index(fields=["is_red_meat"]),
            models.Index(fields=["cooking_method"]),
            models.Index(fields=["has_added_sugar"]),
            GinIndex(fields=["suitable_for"], name="recipe_suitable_for_gin"),
        ]

    def __str__(self):
        return self.title


class RecipeAuthor(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонён"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="author_profile")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    motivation_text = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    recipes_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "recipe_authors"
        indexes = [models.Index(fields=["user_id"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Author({self.user}, {self.status})"


class DeletedRecipe(models.Model):
    """Рецепты, удалённые администратором. Используются для аудита и восстановления."""

    original_id = models.IntegerField(db_index=True)
    title = models.CharField(max_length=512)
    data = models.JSONField()
    deleted_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "deleted_recipes"
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"Deleted({self.original_id}, {self.title[:40]})"


class RecipeFavorite(models.Model):
    """Любимое/нелюбимое (per-user). is_favorite=True — любимое, False — нелюбимое."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipe_favorites")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="favorites")
    is_favorite = models.BooleanField(default=True, help_text="True=любимое, False=нелюбимое")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recipe_favorites"
        unique_together = [("user", "recipe")]
        indexes = [
            models.Index(fields=["user", "is_favorite"]),
            models.Index(fields=["recipe"]),
        ]

    def __str__(self):
        tag = "fav" if self.is_favorite else "dis"
        return f"{tag}({self.user_id}→{self.recipe_id})"
PYEOF

echo
echo "=== [3/8] write apps/recipes/filters.py (extended) ==="
cat > backend/apps/recipes/filters.py <<'PYEOF'
"""
Recipe filters (MG-recipes-screen):

Все фильтры работают независимо и комбинируемы (AND между параметрами).

- ``meal_type`` — приём пищи (suitable_for содержит breakfast/lunch/dinner/snack).
- ``dish_type`` — вид блюда (по categories: суп/салат/выпечка/…).
- ``food_group`` — основной продукт (grain/protein/vegetable/…).
- ``country`` — страна (icontains).
- ``ingredients_all`` / ``ingredients_any`` — список имён ингредиентов (Python icontains).
- ``fridge_ingredients`` — список имён продуктов из холодильника; не фильтрует, а
  *аннотирует* ``fridge_match_count`` (сортировка в view).
- ``exclude_allergens`` — true/false. Если true, исключить рецепты, содержащие
  любой allergen из ``request.user.allergies``.
- ``favorite`` — true (только любимые) / false (только нелюбимые).
- ``calories_min`` / ``calories_max`` — оставлено как было.
- ``category`` (deprecated) — оставлено для совместимости.
"""
from __future__ import annotations

from django_filters import rest_framework as filters

from .models import Recipe


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _ingredient_names(recipe: Recipe) -> list[str]:
    out = []
    for ing in recipe.ingredients or []:
        if isinstance(ing, dict):
            name = ing.get("name")
            if name:
                out.append(_normalize(str(name)))
    return out


def _recipe_matches_any(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    return any(any(n in name for name in names) for n in needles)


def _recipe_matches_all(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    for n in needles:
        if not any(n in name for name in names):
            return False
    return True


def _recipe_fridge_score(recipe: Recipe, needles: list[str]) -> int:
    names = _ingredient_names(recipe)
    score = 0
    for n in needles:
        if any(n in name for name in names):
            score += 1
    return score


class RecipeFilter(filters.FilterSet):
    # legacy
    category = filters.CharFilter(method="filter_category")
    is_custom = filters.BooleanFilter()
    food_group = filters.CharFilter(field_name="food_group", lookup_expr="exact")
    author = filters.NumberFilter(field_name="author_id")
    country = filters.CharFilter(lookup_expr="icontains")
    calories_min = filters.NumberFilter(method="filter_calories_min")
    calories_max = filters.NumberFilter(method="filter_calories_max")
    # MG-recipes-screen
    meal_type = filters.CharFilter(method="filter_meal_type")
    dish_type = filters.CharFilter(method="filter_dish_type")
    protein_type = filters.CharFilter(field_name="protein_type", lookup_expr="exact")
    grain_type = filters.CharFilter(field_name="grain_type", lookup_expr="exact")
    ingredients_all = filters.CharFilter(method="filter_ingredients_all")
    ingredients_any = filters.CharFilter(method="filter_ingredients_any")
    exclude_allergens = filters.BooleanFilter(method="filter_exclude_allergens")
    favorite = filters.BooleanFilter(method="filter_favorite")
    # fridge: не фильтрует, передаётся отдельно через view (нужно для annotate)

    class Meta:
        model = Recipe
        fields = [
            "category",
            "country",
            "is_custom",
            "author",
            "meal_type",
            "dish_type",
            "calories_min",
            "calories_max",
            "food_group",
            "protein_type",
            "grain_type",
            "ingredients_all",
            "ingredients_any",
            "exclude_allergens",
            "favorite",
        ]

    # ─── legacy ───────────────────────────────────────────────────────────

    def filter_category(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)

    # ─── meal type via suitable_for ───────────────────────────────────────

    def filter_meal_type(self, queryset, name, value):
        v = _normalize(value)
        if not v:
            return queryset
        # suitable_for — JSONField со списком меток; используем jsonb contains
        return queryset.filter(suitable_for__contains=[v])

    # ─── dish type via categories (icontains) ─────────────────────────────

    def filter_dish_type(self, queryset, name, value):
        v = _normalize(value)
        if not v:
            return queryset
        return queryset.filter(categories__icontains=v)

    # ─── calories ─────────────────────────────────────────────────────────

    def filter_calories_min(self, queryset, name, value):
        ids = []
        for r in queryset.only("id", "nutrition"):
            try:
                cal = float((r.nutrition or {}).get("calories", {}).get("value", 0) or 0)
                if cal >= float(value):
                    ids.append(r.pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)

    def filter_calories_max(self, queryset, name, value):
        ids = []
        for r in queryset.only("id", "nutrition"):
            try:
                cal = float((r.nutrition or {}).get("calories", {}).get("value", 0) or 0)
                if cal <= float(value):
                    ids.append(r.pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)

    # ─── ingredients (Python icontains; MG-recipes-screen Q-Совпадение) ───

    def _parse_csv(self, value: str) -> list[str]:
        return [_normalize(p) for p in (value or "").split(",") if p.strip()]

    def filter_ingredients_all(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = [r.pk for r in queryset.only("id", "ingredients") if _recipe_matches_all(r, needles)]
        return queryset.filter(pk__in=ids)

    def filter_ingredients_any(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = [r.pk for r in queryset.only("id", "ingredients") if _recipe_matches_any(r, needles)]
        return queryset.filter(pk__in=ids)

    # ─── allergens (по пользователю) ──────────────────────────────────────

    def filter_exclude_allergens(self, queryset, name, value):
        if not value:
            return queryset
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            return queryset
        allergens = user.allergies if isinstance(user.allergies, list) else []
        allergens = [_normalize(str(a)) for a in allergens if a]
        if not allergens:
            return queryset
        good_ids = []
        for r in queryset.only("id", "ingredients"):
            if not _recipe_matches_any(r, allergens):
                good_ids.append(r.pk)
        return queryset.filter(pk__in=good_ids)

    # ─── favorites ─────────────────────────────────────────────────────────

    def filter_favorite(self, queryset, name, value):
        """favorite=true → только is_favorite=True; favorite=false → is_favorite=False."""
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            return queryset.none() if value else queryset
        from .models import RecipeFavorite as RF

        ids = RF.objects.filter(user=user, is_favorite=bool(value)).values_list("recipe_id", flat=True)
        return queryset.filter(pk__in=list(ids))
PYEOF

echo
echo "=== [4/8] write apps/recipes/serializers.py (add is_favorite, fridge_match_count) ==="
cat > backend/apps/recipes/serializers.py <<'PYEOF'
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Recipe, RecipeAuthor, RecipeFavorite

User = get_user_model()


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


class RecipeListSerializer(_FavoriteStateMixin, serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)
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
            )
            + CLASSIFICATION_FIELDS
            + MG501_FIELDS
        )

    def get_fridge_match_count(self, obj):
        scores = self.context.get("fridge_scores")
        if not scores:
            return None
        return scores.get(obj.id, 0)


class RecipeDetailSerializer(_FavoriteStateMixin, serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True, default=None)

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
            )
            + CLASSIFICATION_FIELDS
            + MG501_FIELDS
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
PYEOF

echo
echo "=== [5/8] write apps/recipes/views.py (favorite endpoint + fridge scoring + filter cache) ==="
cat > backend/apps/recipes/views.py <<'PYEOF'
from django.db.models import Case, IntegerField, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import RecipeFilter, _recipe_fridge_score
from .models import DeletedRecipe, Recipe, RecipeAuthor, RecipeFavorite
from .permissions import IsAuthorOrAdmin, IsRecipeAuthorRole
from .serializers import (
    RecipeAuthorSerializer,
    RecipeDetailSerializer,
    RecipeFavoriteWriteSerializer,
    RecipeListSerializer,
    RecipeWriteSerializer,
)


class RecipeCountryListView(generics.ListAPIView):
    """GET /recipes/countries/ — список стран из БД."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        countries = (
            Recipe.objects.filter(is_published=True)
            .exclude(country__isnull=True)
            .exclude(country="")
            .values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )
        return Response(sorted(set(c.strip() for c in countries if c and c.strip())))


def _parse_csv(value):
    if not value:
        return []
    return [p.strip().lower() for p in str(value).split(",") if p.strip()]


class RecipeViewSet(ModelViewSet):
    queryset = Recipe.objects.none()
    filterset_class = RecipeFilter
    search_fields = ["title", "categories", "country"]
    filter_backends = [
        __import__("django_filters").rest_framework.DjangoFilterBackend,
        __import__("rest_framework").filters.SearchFilter,
    ]

    def get_queryset(self):
        return (
            Recipe.objects.filter(is_published=True)
            .select_related("author")
            .annotate(
                has_image=Case(
                    When(image_url__isnull=False, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("-has_image", "-created_at")
        )

    def get_permissions(self):
        if self.action in ("create",):
            return [permissions.IsAuthenticated(), IsRecipeAuthorRole()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsAuthorOrAdmin()]
        if self.action in ("favorite",):
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action == "list":
            return RecipeListSerializer
        if self.action in ("create", "update", "partial_update"):
            return RecipeWriteSerializer
        if self.action == "favorite":
            return RecipeFavoriteWriteSerializer
        return RecipeDetailSerializer

    # ─── list: extra context (fridge scoring + favorites cache + sort) ────

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        request = self.request
        # Avoid running twice on retrieve etc.
        if self.action == "list" and request is not None:
            # Pre-fetch favorites for current page → batch (filled in list())
            ctx.setdefault("favorites_cache", {})
            ctx.setdefault("fridge_scores", {})
        return ctx

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # ── fridge ranking: sort whole queryset by match count desc, then default order
        fridge_csv = request.query_params.get("fridge_ingredients")
        fridge_needles = _parse_csv(fridge_csv)
        fridge_scores: dict[int, int] = {}

        if fridge_needles:
            # Compute scores across queryset; pick top-N by score.
            scored = []
            for r in queryset.only("id", "ingredients"):
                s = _recipe_fridge_score(r, fridge_needles)
                scored.append((r.pk, s))
            scored.sort(key=lambda x: (-x[1], -x[0]))
            ordered_ids = [pk for pk, s in scored if s > 0] or [pk for pk, _ in scored]
            fridge_scores = {pk: s for pk, s in scored}
            # rebuild queryset preserving order via Case/When
            preserved = Case(
                *[When(pk=pk, then=Value(idx)) for idx, pk in enumerate(ordered_ids)],
                output_field=IntegerField(),
            )
            queryset = (
                Recipe.objects.filter(pk__in=ordered_ids)
                .select_related("author")
                .annotate(_order=preserved)
                .order_by("_order")
            )

        page = self.paginate_queryset(queryset)

        # ── favorites cache for current page
        if request.user.is_authenticated and page is not None:
            page_ids = [r.pk for r in page]
            favs = RecipeFavorite.objects.filter(user=request.user, recipe_id__in=page_ids)
            fav_cache = {f.recipe_id: f for f in favs}
        else:
            fav_cache = {}

        ctx = self.get_serializer_context()
        ctx["favorites_cache"] = fav_cache
        ctx["fridge_scores"] = fridge_scores

        if page is not None:
            serializer = RecipeListSerializer(page, many=True, context=ctx)
            return self.get_paginated_response(serializer.data)
        serializer = RecipeListSerializer(queryset, many=True, context=ctx)
        return Response(serializer.data)

    @extend_schema(responses={200: RecipeDetailSerializer})
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        recipe = self.get_object()

        snapshot = {
            "id": recipe.id,
            "title": recipe.title,
            "cook_time": recipe.cook_time,
            "servings": recipe.servings,
            "ingredients": recipe.ingredients,
            "steps": recipe.steps,
            "nutrition": recipe.nutrition,
            "categories": recipe.categories,
            "image_url": recipe.image_url,
            "video_url": recipe.video_url,
            "source_url": recipe.source_url,
            "country": recipe.country,
            "is_custom": recipe.is_custom,
            "is_published": recipe.is_published,
            "created_at": str(recipe.created_at),
            "updated_at": str(recipe.updated_at),
        }
        DeletedRecipe.objects.create(
            original_id=recipe.id,
            title=recipe.title,
            data=snapshot,
            deleted_by=request.user if request.user.is_authenticated else None,
        )
        recipe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=RecipeWriteSerializer,
        responses={201: RecipeDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out = RecipeDetailSerializer(recipe, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=RecipeWriteSerializer,
        responses={200: RecipeDetailSerializer},
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out = RecipeDetailSerializer(recipe, context={"request": request})
        return Response(out.data)

    # ─── POST/DELETE /recipes/{id}/favorite/ ──────────────────────────────

    @extend_schema(
        request=RecipeFavoriteWriteSerializer,
        responses={
            200: {"type": "object", "properties": {
                "is_favorite": {"type": "boolean"},
                "is_disliked": {"type": "boolean"},
            }},
        },
    )
    @action(detail=True, methods=["post", "delete"], url_path="favorite")
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        if request.method == "DELETE":
            RecipeFavorite.objects.filter(user=user, recipe=recipe).delete()
            return Response({"is_favorite": False, "is_disliked": False})

        serializer = RecipeFavoriteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_fav = bool(serializer.validated_data["is_favorite"])

        obj, _ = RecipeFavorite.objects.update_or_create(
            user=user, recipe=recipe, defaults={"is_favorite": is_fav}
        )
        return Response({"is_favorite": obj.is_favorite, "is_disliked": not obj.is_favorite})


class RecipeAuthorApplyView(generics.CreateAPIView):
    """Подать заявку на роль автора рецептов."""

    serializer_class = RecipeAuthorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if RecipeAuthor.objects.filter(user=self.request.user).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Заявка уже подана.")
        serializer.save(user=self.request.user)
PYEOF

echo
echo "=== [6/8] update apps/recipes/admin.py (register RecipeFavorite) ==="
cat > backend/apps/recipes/admin.py <<'PYEOF'
from django.contrib import admin

from .models import Recipe, RecipeAuthor, RecipeFavorite


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "country", "is_custom", "is_published", "author", "created_at")
    list_filter = ("is_custom", "is_published", "country")
    search_fields = ("title", "legacy_id")
    raw_id_fields = ("author",)
    readonly_fields = ("legacy_id", "created_at", "updated_at")
    actions = ["publish", "unpublish"]

    @admin.action(description="Опубликовать выбранные")
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Снять с публикации")
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "applied_at", "approved_at")
    list_filter = ("status",)
    raw_id_fields = ("user",)
    actions = ["approve", "reject"]

    @admin.action(description="Одобрить заявки")
    def approve(self, request, queryset):
        from django.utils import timezone

        from apps.users.models import User

        now = timezone.now()
        for obj in queryset:
            obj.status = "approved"
            obj.approved_at = now
            obj.save(update_fields=["status", "approved_at"])
            User.objects.filter(id=obj.user_id).update(user_type="recipe_author")

    @admin.action(description="Отклонить заявки")
    def reject(self, request, queryset):
        queryset.update(status="rejected")


@admin.register(RecipeFavorite)
class RecipeFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "recipe", "is_favorite", "created_at")
    list_filter = ("is_favorite",)
    raw_id_fields = ("user", "recipe")
    search_fields = ("recipe__title", "user__email", "user__name")
PYEOF

echo
echo "=== [7/8] generate migration via docker ==="
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
$COMPOSE exec -T backend python manage.py makemigrations recipes --name recipe_favorite
$COMPOSE exec -T backend python manage.py migrate recipes

echo
echo "=== [8/8] run tests ==="
$COMPOSE exec -T backend pytest -q apps/recipes/ --tb=line --no-header 2>&1 | tail -30 || true

echo
echo "DONE."
