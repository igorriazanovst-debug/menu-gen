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
