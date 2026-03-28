from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from .models import FridgeItem, Product
from .serializers import (
    BarcodeLookupSerializer,
    FridgeItemSerializer,
    FridgeItemWriteSerializer,
    ProductSerializer,
)


def _get_family(user):
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    return membership.family if membership else None


class FridgeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
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
            from django.utils import timezone
            import datetime

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
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=BarcodeLookupSerializer, responses={200: ProductSerializer})
    def post(self, request):
        serializer = BarcodeLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data["barcode"]
        try:
            product = Product.objects.get(barcode=barcode)
            return Response(ProductSerializer(product).data)
        except Product.DoesNotExist:
            return Response({"detail": "Продукт не найден."}, status=status.HTTP_404_NOT_FOUND)


class ProductSearchView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    search_fields = ["name"]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Product.objects.none()
        return Product.objects.filter(name__icontains=q)[:20]
