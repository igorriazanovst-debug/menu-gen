from django.db.models import Case, IntegerField, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import RecipeFilter
from .made_photos import create_made_photo_from_b64  # MG_MADEPHOTO
from .models import DeletedRecipe, Recipe, RecipeAuthor, RecipeFavorite, RecipeMadePhoto
from .permissions import IsAuthorOrAdmin, IsRecipeAuthorRole
from .serializers import (
    RecipeAuthorSerializer,
    RecipeDetailSerializer,
    RecipeFavoriteWriteSerializer,
    RecipeListSerializer,
    RecipeMadePhotoSerializer,
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
        if self.action in ("favorite", "made_photos", "delete_made_photo"):
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
            from .filters import _names_from_raw

            scored = []
            for pk, ingredients in queryset.values_list("id", "ingredients"):
                names = _names_from_raw(ingredients)
                score = sum(1 for n in fridge_needles if any(n in name for name in names))
                scored.append((pk, score))
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
            200: {
                "type": "object",
                "properties": {
                    "is_favorite": {"type": "boolean"},
                    "is_disliked": {"type": "boolean"},
                },
            },
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

        obj, _ = RecipeFavorite.objects.update_or_create(user=user, recipe=recipe, defaults={"is_favorite": is_fav})
        return Response({"is_favorite": obj.is_favorite, "is_disliked": not obj.is_favorite})

    # ─── MG_MADEPHOTO: «я приготовил — вот фото» ───────────────────────────────
    @extend_schema(responses={200: RecipeMadePhotoSerializer(many=True)})
    @action(detail=True, methods=["get", "post"], url_path="made-photos")
    def made_photos(self, request, pk=None):
        """GET — фото приготовления текущего пользователя; POST {image_b64} — добавить."""
        recipe = self.get_object()
        user = request.user

        if request.method == "POST":
            b64 = request.data.get("image_b64")
            photo = create_made_photo_from_b64(user, recipe, b64)
            if photo is None:
                return Response({"detail": "Не удалось прочитать изображение."}, status=status.HTTP_400_BAD_REQUEST)
            data = RecipeMadePhotoSerializer(photo, context={"request": request}).data
            return Response(data, status=status.HTTP_201_CREATED)

        qs = RecipeMadePhoto.objects.filter(user=user, recipe=recipe)
        data = RecipeMadePhotoSerializer(qs, many=True, context={"request": request}).data
        return Response(data)

    @extend_schema(responses={204: None})
    @action(detail=True, methods=["delete"], url_path="made-photos/(?P<photo_id>[0-9]+)")
    def delete_made_photo(self, request, pk=None, photo_id=None):
        """Удалить своё фото приготовления по id."""
        recipe = self.get_object()
        photo = RecipeMadePhoto.objects.filter(id=photo_id, user=request.user, recipe=recipe).first()
        if photo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeAuthorApplyView(generics.CreateAPIView):
    """Подать заявку на роль автора рецептов."""

    serializer_class = RecipeAuthorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if RecipeAuthor.objects.filter(user=self.request.user).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Заявка уже подана.")
        serializer.save(user=self.request.user)
