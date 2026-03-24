from django_filters import rest_framework as filters

from .models import Recipe


class RecipeFilter(filters.FilterSet):
    category = filters.CharFilter(method="filter_category")
    country = filters.CharFilter(lookup_expr="icontains")
    is_custom = filters.BooleanFilter()
    author = filters.NumberFilter(field_name="author_id")

    class Meta:
        model = Recipe
        fields = ["category", "country", "is_custom", "author"]

    def filter_category(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)
