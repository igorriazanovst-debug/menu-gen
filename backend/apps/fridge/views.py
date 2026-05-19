from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly

from .models import FridgeItem, Product, ProductCategory
from .serializers import (
    BarcodeLookupSerializer,
    FridgeHistoryItemSerializer,
    FridgeItemSerializer,
    FridgeItemWriteSerializer,
    ProductCategorySerializer,
    ProductSerializer,
)
from .services import fetch_product_from_off


def _get_family(user):
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    return membership.family if membership else None


class FridgeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ["unit"]
    search_fields = ["name"]

    def get_family(self):
        if not hasattr(self, "_family"):
            self._family = _get_family(self.request.user)
        return self._family

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FridgeItem.objects.none()
        family = self.get_family()
        if not family:
            return FridgeItem.objects.none()
        qs = (
            FridgeItem.objects.filter(family=family, is_deleted=False)
            .select_related("product")
            .order_by("expiry_date", "name")
        )
        expiring = self.request.query_params.get("expiring_days")
        if expiring:
            import datetime
            from django.utils import timezone
            cutoff = timezone.now().date() + datetime.timedelta(days=int(expiring))
            qs = qs.filter(expiry_date__lte=cutoff, expiry_date__isnull=False)
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FridgeItemWriteSerializer
        return FridgeItemSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["family"] = self.get_family()
        return ctx

    @extend_schema(
        parameters=[OpenApiParameter("expiring_days", int, description="Фильтр: истекает через N дней")],
        responses={200: FridgeItemSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=FridgeItemWriteSerializer, responses={201: FridgeItemSerializer})
    def post(self, request, *args, **kwargs):
        family = self.get_family()
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        out = FridgeItemSerializer(item, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class FridgeItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def get_queryset(self):
        family = _get_family(self.request.user)
        if not family:
            return FridgeItem.objects.none()
        return FridgeItem.objects.filter(family=family, is_deleted=False)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return FridgeItemWriteSerializer
        return FridgeItemSerializer

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])

    @extend_schema(responses={200: FridgeItemSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=FridgeItemWriteSerializer, responses={200: FridgeItemSerializer})
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class BarcodeLookupView(APIView):
    """
    POST /fridge/scan/  body: {"barcode": "..."}
    1) try local Product;  2) try OpenFoodFacts (cache locally);  3) 404.
    """
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    @extend_schema(request=BarcodeLookupSerializer, responses={200: ProductSerializer})
    def post(self, request):
        serializer = BarcodeLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data["barcode"].strip()
        if not barcode:
            return Response({"detail": "barcode required"}, status=status.HTTP_400_BAD_REQUEST)

        product = Product.objects.filter(barcode=barcode).first()
        if product is not None:
            data = ProductSerializer(product).data
            data["source"] = "local"
            return Response(data)

        product = fetch_product_from_off(barcode)
        if product is not None:
            data = ProductSerializer(product).data
            data["source"] = "openfoodfacts"
            return Response(data, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Продукт не найден.", "barcode": barcode},
            status=status.HTTP_404_NOT_FOUND,
        )


class FridgeItemDetailsView(APIView):
    """
    GET /fridge/<int:pk>/details/
    Returns extended info for the fridge item: nutrition (from Product if FK
    set), expiry days-left, menu-usage stats for last 30 days.
    """
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def get(self, request, pk: int):
        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        item = (
            FridgeItem.objects
            .filter(family=family, is_deleted=False, pk=pk)
            .select_related("product")
            .first()
        )
        if not item:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        # days_left
        days_left = None
        if item.expiry_date is not None:
            from django.utils import timezone as _tz
            days_left = (item.expiry_date - _tz.now().date()).days

        product_data = None
        if item.product is not None:
            product_data = ProductSerializer(item.product).data

        # usage_30d: name source is product.name if FK exists, else item.name
        from .services import get_menu_usage_30d
        name_for_lookup = (item.product.name if item.product else item.name)
        usage = get_menu_usage_30d(family, name_for_lookup, days=30)

        return Response({
            "item": FridgeItemSerializer(item, context={"request": request}).data,
            "product": product_data,
            "days_left": days_left,
            "usage_30d": usage,
        })


class ProductSearchView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    serializer_class = ProductSerializer
    search_fields = ["name"]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Product.objects.none()
        return Product.objects.filter(name__icontains=q)[:20]


# ─── MG-609: category list ──────────────────────────────────────────────────
class ProductCategoryListView(generics.ListAPIView):
    """GET /fridge/categories/  — list active product categories."""
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    serializer_class = ProductCategorySerializer
    pagination_class = None

    def get_queryset(self):
        return ProductCategory.objects.filter(is_active=True).order_by("sort_order", "name_ru")


class ProductListView(generics.ListAPIView):
    """GET /fridge/products/?category=<slug|id>&seed=1  — list products."""
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    serializer_class = ProductSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Product.objects.select_related("category_fk").all()
        cat = self.request.query_params.get("category")
        if cat:
            if str(cat).isdigit():
                qs = qs.filter(category_fk_id=int(cat))
            else:
                qs = qs.filter(category_fk__slug=cat)
        if self.request.query_params.get("seed") in ("1", "true"):
            qs = qs.filter(is_seed=True)
        return qs.order_by("category_fk__sort_order", "name")[:500]


class FridgeHistoryView(APIView):
    """GET /fridge/products/history/?limit=50 — aggregated history for the family."""
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def get(self, request):
        family = _get_family(request.user)
        if not family:
            return Response([], status=status.HTTP_200_OK)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 50)), 200))
        except (TypeError, ValueError):
            limit = 50

        from django.db.models import Count, Max
        rows = (
            FridgeItem.objects
            .filter(family=family)
            .values(
                "name",
                "product_id",
                "product__category_fk_id",
                "product__category_fk__slug",
                "product__category_fk__name_ru",
                "product__category_fk__icon",
                "product__category_fk__color",
                "product__default_unit",
                "product__image_url",
                "unit",
            )
            .annotate(times_used=Count("id"), last_used=Max("created_at"))
            .order_by("-last_used")[:limit]
        )

        out, seen = [], set()
        for r in rows:
            key = (r["name"] or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({
                "name": r["name"],
                "product_id": r["product_id"],
                "category_id": r["product__category_fk_id"],
                "category_slug": r["product__category_fk__slug"] or "",
                "category_name": r["product__category_fk__name_ru"] or "",
                "category_icon": r["product__category_fk__icon"] or "",
                "category_color": r["product__category_fk__color"] or "",
                "default_unit": r["product__default_unit"] or r["unit"] or "",
                "image_url": r["product__image_url"] or "",
                "times_used": r["times_used"],
                "last_used": r["last_used"],
            })
        return Response(FridgeHistoryItemSerializer(out, many=True).data)
