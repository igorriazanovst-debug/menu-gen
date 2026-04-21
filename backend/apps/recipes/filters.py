from django_filters import rest_framework as filters

from .models import Recipe


class RecipeFilter(filters.FilterSet):
    category    = filters.CharFilter(method="filter_category")
    country     = filters.CharFilter(lookup_expr="icontains")
    is_custom   = filters.BooleanFilter()
    author      = filters.NumberFilter(field_name="author_id")
    meal_type   = filters.CharFilter(method="filter_meal_type")
    calories_min = filters.NumberFilter(method="filter_calories_min")
    calories_max = filters.NumberFilter(method="filter_calories_max")

    class Meta:
        model  = Recipe
        fields = ["category", "country", "is_custom", "author", "meal_type",
                  "calories_min", "calories_max"]

    def filter_category(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)

    def filter_meal_type(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)

    def filter_calories_min(self, queryset, name, value):
        result = []
        for r in queryset:
            try:
                cal = float(r.nutrition.get("calories", {}).get("value", 0) or 0)
                if cal >= float(value):
                    result.append(r.pk)
            except (TypeError, ValueError):
                pass
        return queryset.filter(pk__in=result)

    def filter_calories_max(self, queryset, name, value):
        result = []
        for r in queryset:
            try:
                cal = float(r.nutrition.get("calories", {}).get("value", 0) or 0)
                if cal <= float(value):
                    result.append(r.pk)
            except (TypeError, ValueError):
                pass
        return queryset.filter(pk__in=result)
