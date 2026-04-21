from django.db.models import Case, IntegerField, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import RecipeFilter
from .models import Recipe, RecipeAuthor
from .permissions import IsAuthorOrAdmin, IsRecipeAuthorRole
from .serializers import (
    RecipeAuthorSerializer,
    RecipeDetailSerializer,
    RecipeListSerializer,
    RecipeWriteSerializer,
)


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
