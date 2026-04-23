from django.db.models import Case, IntegerField, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from django.db.models import Count
from .filters import RecipeFilter
from .models import DeletedRecipe, Recipe, RecipeAuthor
from .permissions import IsAuthorOrAdmin, IsRecipeAuthorRole
from .serializers import (
    RecipeAuthorSerializer,
    RecipeDetailSerializer,
    RecipeListSerializer,
    RecipeWriteSerializer,
)


class RecipeCountryListView(generics.ListAPIView):
    """GET /recipes/countries/ — список стран из БД."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        countries = (
            Recipe.objects
            .filter(is_published=True)
            .exclude(country__isnull=True)
            .exclude(country='')
            .values_list('country', flat=True)
            .distinct()
            .order_by('country')
        )
        return Response(sorted(set(c.strip() for c in countries if c and c.strip())))


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
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action == "list":
            return RecipeListSerializer
        if self.action in ("create", "update", "partial_update"):
            return RecipeWriteSerializer
        return RecipeDetailSerializer

    @extend_schema(responses={200: RecipeDetailSerializer})
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


    def destroy(self, request, *args, **kwargs):
        recipe = self.get_object()
        import json
        from django.forms.models import model_to_dict
        snapshot = {
            "id":          recipe.id,
            "title":       recipe.title,
            "cook_time":   recipe.cook_time,
            "servings":    recipe.servings,
            "ingredients": recipe.ingredients,
            "steps":       recipe.steps,
            "nutrition":   recipe.nutrition,
            "categories":  recipe.categories,
            "image_url":   recipe.image_url,
            "video_url":   recipe.video_url,
            "source_url":  recipe.source_url,
            "country":     recipe.country,
            "is_custom":   recipe.is_custom,
            "is_published":recipe.is_published,
            "created_at":  str(recipe.created_at),
            "updated_at":  str(recipe.updated_at),
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


class RecipeAuthorApplyView(generics.CreateAPIView):
    """Подать заявку на роль автора рецептов."""

    serializer_class = RecipeAuthorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if RecipeAuthor.objects.filter(user=self.request.user).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Заявка уже подана.")
        serializer.save(user=self.request.user)
