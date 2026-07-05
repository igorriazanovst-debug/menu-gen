from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
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
    RecognizedProductSerializer,
    RecognizePhotoRequestSerializer,
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
            .select_related("product", "product__category_fk", "category_fk")  # MG_T07
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
            # MENUGEN_LOCAL_ENRICH: a product cached before the category/KBJU
            # fix may lack category_fk and/or nutrition. Backfill it on read so
            # repeat scans group correctly and show KBJU.
            from .services import enrich_existing_product

            enrich_existing_product(product)
            data = ProductSerializer(product).data
            data["source"] = "local"
            return Response(data)

        product = fetch_product_from_off(barcode)
        if product is not None:
            data = ProductSerializer(product).data
            # MENUGEN_SCAN_SOURCE: product may be enriched via OFF or GPT fallback
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
        item = FridgeItem.objects.filter(family=family, is_deleted=False, pk=pk).select_related("product").first()
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

        name_for_lookup = item.product.name if item.product else item.name
        usage = get_menu_usage_30d(family, name_for_lookup, days=30)

        return Response(
            {
                "item": FridgeItemSerializer(item, context={"request": request}).data,
                "product": product_data,
                "days_left": days_left,
                "usage_30d": usage,
            }
        )


class ProductSearchView(generics.ListAPIView):
    # freemium: каталог продуктов (КБЖУ) открыт для поиска free-юзерам —
    # используется ручным добавлением в дневник. Это общий справочник, а не
    # данные холодильника семьи.
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    search_fields = ["name"]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Product.objects.none()
        # Матчим и по имени, и по синонимам (ProductAlias): «огурец» -> «Огурцы».
        from .aliases import normalize_alias

        cond = Q(name__icontains=q)
        qn = normalize_alias(q)
        if qn:
            cond |= Q(aliases__alias_norm__icontains=qn)
        return Product.objects.filter(cond).distinct().order_by("name")[:20]


# ─── MG_ALLERGEN: freemium collapsed catalog for allergen picking ────────────
class AllergenCatalogView(APIView):
    """GET /fridge/products/catalog/?q=  — схлопнутый список аллергенов.

    Freemium-open (как ProductSearchView): это общий справочник продуктов, а не
    данные холодильника семьи. Варианты одного продукта схлопываются в один
    базовый аллерген (canonical_allergen): «Сыр гауда», «Сыр тёртый» → «Сыр».
    Возвращает список объектов:
        {key, name, category_name, examples: [оригинальные названия]}
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .aliases import canonical_allergen, normalize_alias

        qs = Product.objects.select_related("category_fk").all()
        q = request.query_params.get("q", "").strip()
        if q:
            cond = Q(name__icontains=q)
            qn = normalize_alias(q)
            if qn:
                cond |= Q(aliases__alias_norm__icontains=qn)
            qs = qs.filter(cond).distinct()

        collapsed = {}
        for p in qs.order_by("category_fk__sort_order", "category_fk__name_ru", "name")[:2000]:
            base = canonical_allergen(p.name)
            if not base:
                continue
            entry = collapsed.get(base)
            if entry is None:
                collapsed[base] = {
                    "key": base,
                    "name": base[:1].upper() + base[1:],
                    "category_name": p.category_fk.name_ru if p.category_fk_id else "Прочее",
                    "examples": [p.name],
                }
            elif len(entry["examples"]) < 4 and p.name not in entry["examples"]:
                entry["examples"].append(p.name)

        rows = sorted(collapsed.values(), key=lambda r: (r["category_name"], r["name"]))
        return Response(rows)


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


class FridgeExpiredBulkDeleteView(APIView):
    """
    POST /fridge/expired/delete/
    Body: { "ids": [int, ...]  (optional),
            "all": bool         (optional),
            "drop_history": bool (default False) }
    Deletes expired fridge items. If `all` is true, deletes all currently
    expired items of the family. Otherwise deletes the given `ids`
    (restricted to expired & family-owned).
    drop_history=True  -> hard delete (record vanishes from history).
    drop_history=False -> soft delete (is_deleted=True, stays in history).
    Returns { "deleted": N }.
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def post(self, request):
        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        qs = FridgeItem.objects.filter(
            family=family,
            is_deleted=False,
            expiry_date__isnull=False,
            expiry_date__lt=today,
        )

        if not request.data.get("all"):
            ids = request.data.get("ids") or []
            if not isinstance(ids, list) or not ids:
                return Response({"detail": "Не выбраны позиции."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                ids = [int(x) for x in ids]
            except (TypeError, ValueError):
                return Response({"detail": "Некорректные id."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(id__in=ids)

        drop_history = bool(request.data.get("drop_history", False))
        if drop_history:
            deleted, _ = qs.delete()
        else:
            deleted = qs.update(is_deleted=True)

        return Response({"deleted": deleted})


class FridgeHistoryEntryView(APIView):
    """
    DELETE /fridge/products/history/<name>/
    Query: ?drop_fridge=0|1  (default 0)

    drop_fridge=0 (default): "remove from history only" — hard-deletes the
        records with this name that are NOT in the fridge now (is_deleted=True).
        Active items stay in the fridge.
    drop_fridge=1: hard-deletes ALL records with this name (active + soft-deleted),
        i.e. removes from fridge and from history at once.

    Name match is case-insensitive exact (iexact) within the family.
    Returns { "deleted": N }.
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def delete(self, request, name: str):
        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        name = (name or "").strip()
        if not name:
            return Response({"detail": "Пустое имя."}, status=status.HTTP_400_BAD_REQUEST)

        qs = FridgeItem.objects.filter(family=family, name__iexact=name)
        drop_fridge = str(request.query_params.get("drop_fridge", "0")).lower() in ("1", "true")
        if not drop_fridge:
            qs = qs.filter(is_deleted=True)

        deleted, _ = qs.delete()
        return Response({"deleted": deleted})


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
            FridgeItem.objects.filter(family=family)
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
            out.append(
                {
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
                }
            )
        return Response(FridgeHistoryItemSerializer(out, many=True).data)


# >>> MENUGEN_VISION_BEGIN (managed block — do not edit between markers)


# ─── Photo recognition endpoint (OCR + LLM) ───────────────────────────
class RecognizePhotoView(APIView):
    """
    POST /fridge/recognize-photo/
    Body (multipart): image=<file>, mode=single|multi
       or (json):     {"image_b64": "...", "mode": "single|multi"}

    Pipeline: Yandex Vision OCR (text) -> text LLM (name extraction).
    Returns recognized product(s) for client-side prefill; does NOT create
    fridge items (creation stays in FridgeListCreateView).

    Response:
      single -> {"mode":"single","product":{...}|null,"raw_text":"..."}
      multi  -> {"mode":"multi","products":[{...}],"raw_text":"..."}
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _match_category(self, label: str):
        """Match category label to ProductCategory.

        The extraction prompt now returns a category *slug* from the allowed
        list, so try exact slug first; fall back to fuzzy name match for
        backward compatibility / free-form labels.
        """
        label = (label or "").strip()
        if not label:
            return None
        exact = ProductCategory.objects.filter(is_active=True, slug=label).first()
        if exact is not None:
            return exact
        from django.db.models import Q

        return (
            ProductCategory.objects.filter(is_active=True)
            .filter(Q(name_ru__icontains=label) | Q(slug__icontains=label) | Q(name_en__icontains=label))
            .order_by("sort_order", "name_ru")
            .first()
        )

    def _enrich(self, item: dict) -> dict:
        cat = self._match_category(item.get("category", ""))
        if cat is not None:
            item = {
                **item,
                "category_id": cat.id,
                "category_slug": cat.slug,
                "category_name": cat.name_ru,
                "category_icon": cat.icon,
                "category_color": cat.color,
            }
        else:
            item = {
                **item,
                "category_id": None,
                "category_slug": None,
                "category_name": None,
                "category_icon": None,
                "category_color": None,
            }
        return item

    @extend_schema(
        request=RecognizePhotoRequestSerializer,
        responses={200: OpenApiResponse(description="Recognized product(s)")},
    )
    def post(self, request):
        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        req = RecognizePhotoRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        mode = req.validated_data["mode"]

        # read image bytes + mime from file or base64
        image_bytes = None
        mime = "image/jpeg"
        upload = req.validated_data.get("image")
        if upload is not None:
            image_bytes = upload.read()
            mime = getattr(upload, "content_type", None) or mime
        else:
            import base64 as _b64

            b64 = req.validated_data.get("image_b64", "") or ""
            if "," in b64 and b64.strip().lower().startswith("data:"):
                # data URL: data:image/png;base64,XXXX
                head, b64 = b64.split(",", 1)
                if "image/png" in head:
                    mime = "image/png"
                elif "application/pdf" in head:
                    mime = "application/pdf"
            try:
                image_bytes = _b64.b64decode(b64, validate=False)
            except Exception:
                return Response({"detail": "Некорректный image_b64."}, status=status.HTTP_400_BAD_REQUEST)

        if not image_bytes:
            return Response({"detail": "Пустое изображение."}, status=status.HTTP_400_BAD_REQUEST)

        # size guard
        max_mb = float(getattr(settings, "OCR_MAX_IMAGE_MB", 10))
        if len(image_bytes) > max_mb * 1024 * 1024:
            return Response(
                {"detail": f"Изображение больше {int(max_mb)} МБ."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        from apps.common.vision import VisionConfigError, VisionRequestError, recognize_products

        try:
            products, raw_text = recognize_products(image_bytes, mime=mime, mode=mode)
        except VisionConfigError as exc:
            return Response(
                {"detail": f"Конфигурация распознавания: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except VisionRequestError as exc:
            return Response(
                {"detail": f"Ошибка распознавания: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        enriched = [self._enrich(p) for p in products]
        out = RecognizedProductSerializer(enriched, many=True).data

        if mode == "single":
            return Response({"mode": "single", "product": (out[0] if out else None), "raw_text": raw_text})
        return Response({"mode": "multi", "products": out, "raw_text": raw_text})


# <<< MENUGEN_VISION_END
