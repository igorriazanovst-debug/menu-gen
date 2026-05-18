#!/usr/bin/env bash
# Fridge add-item v2: backend + mobile + web (corrected settings path)
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
MOB="$ROOT/mobile/menugen_app"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
cd "$ROOT"

TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/fridge_add_v2_${TS}"
mkdir -p "$BAK/backend/fridge" \
         "$BAK/mobile/fridge/bloc" "$BAK/mobile/fridge/screens" \
         "$BAK/mobile/android" "$BAK/mobile" \
         "$BAK/web/api" "$BAK/web/types" "$BAK/web/layout" \
         "$BAK/backend/config"

echo "===== [BACKUP] ====="
cp "$BACKEND/config/settings.py"         "$BAK/backend/config/"
cp "$BACKEND/apps/fridge/models.py"      "$BAK/backend/fridge/"
cp "$BACKEND/apps/fridge/serializers.py" "$BAK/backend/fridge/"
cp "$BACKEND/apps/fridge/views.py"       "$BAK/backend/fridge/"
cp "$BACKEND/apps/fridge/urls.py"        "$BAK/backend/fridge/"
cp "$MOB/pubspec.yaml"                   "$BAK/mobile/"
cp "$MOB/android/app/src/main/AndroidManifest.xml" "$BAK/mobile/android/"
cp -r "$MOB/lib/features/fridge"         "$BAK/mobile/fridge_full"
cp "$WEB/src/App.tsx"                    "$BAK/web/"
cp "$WEB/src/components/layout/Sidebar.tsx" "$BAK/web/layout/"
cp "$WEB/src/types/index.ts"             "$BAK/web/types/"
cp "$WEB/package.json"                   "$BAK/web/"
echo "Backup -> $BAK"

# =================================================================
echo
echo "===== [BACKEND 1/5] Settings: OPENFOODFACTS_* (revert + add via decouple.config) ====="
SETTINGS="$BACKEND/config/settings.py"

# Remove broken block from previous run (lines with os.environ.get for OPENFOODFACTS)
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/config/settings.py")
s = p.read_text()
# Strip the broken trailing OPENFOODFACTS block (if present)
marker = "# ── Fridge: OpenFoodFacts fallback for unknown barcodes ──────────────"
if marker in s:
    s = s.split(marker)[0].rstrip() + "\n"
# Append new block using decouple.config
addition = '''

# ── Fridge: OpenFoodFacts fallback for unknown barcodes ──────────────
OPENFOODFACTS_BASE_URL = config(
    "OPENFOODFACTS_BASE_URL",
    default="https://world.openfoodfacts.org",
)
OPENFOODFACTS_TIMEOUT = config("OPENFOODFACTS_TIMEOUT", default=4.0, cast=float)
OPENFOODFACTS_USER_AGENT = config(
    "OPENFOODFACTS_USER_AGENT",
    default="MenuGen/1.0 (+https://menugen.local)",
)
'''
p.write_text(s + addition)
print("settings.py rewritten with decouple.config")
PYEOF

echo "--- verify settings.py syntax via python -m py_compile in container:"
$COMPOSE exec -T backend python -m py_compile config/settings.py && echo "  syntax OK" || echo "  SYNTAX ERROR"

# =================================================================
echo
echo "===== [BACKEND 2/5] Model: Product.image_url ====="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/fridge/models.py")
s = p.read_text()
if "image_url" in s:
    print("  image_url already in models.py")
else:
    old = '    barcode = models.CharField(max_length=64, null=True, blank=True, unique=True)\n'
    new = (
        '    barcode = models.CharField(max_length=64, null=True, blank=True, unique=True)\n'
        '    image_url = models.URLField(max_length=1024, null=True, blank=True)\n'
    )
    if old not in s:
        raise SystemExit("ERROR: barcode line not found in models.py")
    p.write_text(s.replace(old, new))
    print("  added image_url to Product")
PYEOF

echo "  generating migration..."
$COMPOSE exec -T backend python manage.py makemigrations fridge --name product_image_url 2>&1 | tail -5

echo "  applying migration..."
$COMPOSE exec -T backend python manage.py migrate fridge 2>&1 | tail -5

# =================================================================
echo
echo "===== [BACKEND 3/5] Serializers + Views + Services ====="
cat > "$BACKEND/apps/fridge/serializers.py" <<'PYEOF'
from rest_framework import serializers

from .models import FridgeItem, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id", "name", "category", "default_unit",
            "calories_per_100g", "nutrition", "barcode", "image_url",
        )


class FridgeItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    product_category = serializers.CharField(source="product.category", read_only=True, default=None)
    product_image_url = serializers.CharField(source="product.image_url", read_only=True, default=None)

    class Meta:
        model = FridgeItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_category",
            "product_image_url",
            "name",
            "quantity",
            "unit",
            "expiry_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip()


class FridgeItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FridgeItem
        fields = ("product", "name", "quantity", "unit", "expiry_date")

    def create(self, validated_data):
        family = self.context["family"]
        user = self.context["request"].user
        return FridgeItem.objects.create(
            **validated_data,
            family=family,
            added_by_id=user.id,
        )


class BarcodeLookupSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=64)
PYEOF
echo "  serializers.py written"

cat > "$BACKEND/apps/fridge/services.py" <<'PYEOF'
"""OpenFoodFacts integration: barcode → Product (cached locally)."""
from __future__ import annotations

import logging
from typing import Optional

import requests
from django.conf import settings

from .models import Product

logger = logging.getLogger(__name__)


def _normalize_off_product(raw: dict) -> Optional[dict]:
    """Map OFF product JSON to our Product fields. Returns None if no name."""
    name = (
        raw.get("product_name_ru")
        or raw.get("product_name")
        or raw.get("generic_name_ru")
        or raw.get("generic_name")
        or ""
    ).strip()
    if not name:
        return None

    nutriments = raw.get("nutriments") or {}
    calories = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
    try:
        calories = float(calories) if calories is not None else None
    except (TypeError, ValueError):
        calories = None

    nutrition = {}
    for key, off_key in (
        ("proteins", "proteins_100g"),
        ("fats", "fat_100g"),
        ("carbs", "carbohydrates_100g"),
        ("fiber", "fiber_100g"),
        ("sugars", "sugars_100g"),
    ):
        v = nutriments.get(off_key)
        try:
            if v is not None:
                nutrition[key] = float(v)
        except (TypeError, ValueError):
            pass

    image = (
        raw.get("image_front_url")
        or raw.get("image_url")
        or raw.get("image_small_url")
    )

    category = (raw.get("categories") or "").split(",")[0].strip() if raw.get("categories") else ""

    return {
        "name": name[:255],
        "category": category[:100],
        "default_unit": "",
        "calories_per_100g": calories,
        "nutrition": nutrition,
        "image_url": image[:1024] if image else None,
    }


def fetch_product_from_off(barcode: str) -> Optional[Product]:
    """Fetch from OFF API, save into local Product table, return it. None if not found."""
    base = getattr(settings, "OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org")
    timeout = getattr(settings, "OPENFOODFACTS_TIMEOUT", 4.0)
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")

    url = f"{base}/api/v2/product/{barcode}.json"
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
    except requests.RequestException as e:
        logger.warning("OFF request failed for barcode=%s: %s", barcode, e)
        return None

    if r.status_code != 200:
        logger.info("OFF returned status=%s for barcode=%s", r.status_code, barcode)
        return None

    try:
        body = r.json()
    except ValueError:
        return None

    if body.get("status") != 1:
        return None

    fields = _normalize_off_product(body.get("product") or {})
    if not fields:
        return None

    product, _created = Product.objects.update_or_create(
        barcode=barcode,
        defaults=fields,
    )
    return product
PYEOF
echo "  services.py written"

cat > "$BACKEND/apps/fridge/views.py" <<'PYEOF'
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly

from .models import FridgeItem, Product
from .serializers import (
    BarcodeLookupSerializer,
    FridgeItemSerializer,
    FridgeItemWriteSerializer,
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


class ProductSearchView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]
    serializer_class = ProductSerializer
    search_fields = ["name"]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Product.objects.none()
        return Product.objects.filter(name__icontains=q)[:20]
PYEOF
echo "  views.py written"

# =================================================================
echo
echo "===== [BACKEND 4/5] Tests: OFF fallback ====="
cat > "$BACKEND/apps/fridge/tests/test_barcode_off_fallback.py" <<'PYEOF'
"""Tests for OpenFoodFacts fallback in BarcodeLookupView."""
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import Product
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _family_with_premium():
    user = User.objects.create_user(email="t@t.t", password="x", name="T")
    family = Family.objects.create(name="F", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": "0", "period": "month"},
    )
    from django.utils import timezone
    import datetime
    Subscription.objects.create(
        family=family, plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user


def _auth(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
def test_barcode_found_locally():
    user = _family_with_premium()
    Product.objects.create(name="Молоко", barcode="4601234500000")
    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "4601234500000"}, format="json")
    assert resp.status_code == 200
    assert resp.data["name"] == "Молоко"
    assert resp.data["source"] == "local"


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_fallback_off_creates_product(mock_get):
    user = _family_with_premium()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 1,
        "product": {
            "product_name_ru": "Хлеб бородинский",
            "categories": "Хлеб, выпечка",
            "image_front_url": "https://example.org/img.jpg",
            "nutriments": {
                "energy-kcal_100g": 250,
                "proteins_100g": 8,
                "fat_100g": 1.5,
                "carbohydrates_100g": 50,
                "fiber_100g": 6,
            },
        },
    }
    mock_get.return_value = mock_resp

    c = _auth(user)
    assert not Product.objects.filter(barcode="4607000000000").exists()
    resp = c.post(reverse("fridge-scan"), {"barcode": "4607000000000"}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.data["name"] == "Хлеб бородинский"
    assert resp.data["source"] == "openfoodfacts"
    assert resp.data["image_url"] == "https://example.org/img.jpg"
    cached = Product.objects.get(barcode="4607000000000")
    assert cached.name == "Хлеб бородинский"


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_off_returns_not_found(mock_get):
    user = _family_with_premium()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 0}
    mock_get.return_value = mock_resp

    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "0000000000000"}, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_barcode_off_timeout_returns_404(mock_get):
    import requests
    user = _family_with_premium()
    mock_get.side_effect = requests.Timeout("simulated")

    c = _auth(user)
    resp = c.post(reverse("fridge-scan"), {"barcode": "0000000000001"}, format="json")
    assert resp.status_code == 404
PYEOF
echo "  test_barcode_off_fallback.py written"

echo
echo "  running new tests..."
$COMPOSE exec -T backend pytest apps/fridge/tests/test_barcode_off_fallback.py -v --tb=short 2>&1 | tail -30

# =================================================================
echo
echo "===== [BACKEND 5/5] Fridge regression ====="
$COMPOSE exec -T backend pytest apps/fridge/ --tb=short 2>&1 | tail -15

# =================================================================
echo
echo "===== [MOBILE 1/6] pubspec.yaml deps ====="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/pubspec.yaml")
s = p.read_text()

additions = {
    "mobile_scanner": "  mobile_scanner: ^5.2.3",
    "image_picker":   "  image_picker: ^1.1.2",
    "permission_handler": "  permission_handler: ^11.3.1",
}
lines = s.splitlines(keepends=True)
out = []
inserted = False
for ln in lines:
    out.append(ln)
    if "cached_network_image:" in ln and not inserted:
        for key, val in additions.items():
            if key not in s:
                out.append(val + "\n")
        inserted = True
if not inserted:
    if "mobile_scanner" not in s:
        out.append("\n  mobile_scanner: ^5.2.3\n")
    if "image_picker" not in s:
        out.append("  image_picker: ^1.1.2\n")
    if "permission_handler" not in s:
        out.append("  permission_handler: ^11.3.1\n")

p.write_text("".join(out))
print("pubspec.yaml updated")
PYEOF
grep -E "mobile_scanner|image_picker|permission_handler|cached_network_image" "$MOB/pubspec.yaml"

# =================================================================
echo
echo "===== [MOBILE 2/6] AndroidManifest: CAMERA ====="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/android/app/src/main/AndroidManifest.xml")
s = p.read_text()
if "android.permission.CAMERA" in s:
    print("  CAMERA already present")
else:
    marker = '<uses-permission android:name="android.permission.INTERNET"/>'
    if marker not in s:
        raise SystemExit("ERROR: INTERNET marker not found")
    new = (
        marker
        + '\n    <uses-permission android:name="android.permission.CAMERA"/>'
        + '\n    <uses-feature android:name="android.hardware.camera" android:required="false"/>'
    )
    p.write_text(s.replace(marker, new))
    print("  CAMERA permission added")
PYEOF

# =================================================================
echo
echo "===== [MOBILE 3/6] FridgeBloc rewrite ====="
cat > "$MOB/lib/features/fridge/bloc/fridge_bloc.dart" <<'DARTEOF'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override
  List<Object?> get props => [];
}

class FridgeLoadRequested extends FridgeEvent {
  const FridgeLoadRequested();
}

class FridgeItemAdded extends FridgeEvent {
  final String name;
  final double quantity;
  final String unit;
  final String expiryDate;
  final int? productId;
  const FridgeItemAdded({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.expiryDate,
    this.productId,
  });
  @override
  List<Object?> get props => [name, quantity, unit, expiryDate, productId];
}

class FridgeItemDeleted extends FridgeEvent {
  final int id;
  const FridgeItemDeleted(this.id);
  @override
  List<Object?> get props => [id];
}

abstract class FridgeState extends Equatable {
  const FridgeState();
  @override
  List<Object?> get props => [];
}

class FridgeLoading extends FridgeState {
  const FridgeLoading();
}

class FridgeLoaded extends FridgeState {
  final List<Map<String, dynamic>> items;
  const FridgeLoaded({required this.items});
  @override
  List<Object?> get props => [items];
}

class FridgePremiumLocked extends FridgeState {
  final String message;
  final bool isWrite;
  const FridgePremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class FridgeError extends FridgeState {
  final String message;
  const FridgeError(this.message);
  @override
  List<Object?> get props => [message];
}

class FridgeBloc extends Bloc<FridgeEvent, FridgeState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  FridgeBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const FridgeLoading()) {
    on<FridgeLoadRequested>(_onLoad);
    on<FridgeItemAdded>(_onAdd);
    on<FridgeItemDeleted>(_onDelete);
  }

  FridgeState _toErrorState(Object err, {required bool isWrite}) {
    if (err is ApiException && err.isPremiumLocked) {
      premiumGate?.reportLock(
        feature: 'fridge',
        isWrite: isWrite,
        message: err.message,
      );
      return FridgePremiumLocked(message: err.message, isWrite: isWrite);
    }
    final msg = err is ApiException ? err.message : err.toString();
    return FridgeError(msg);
  }

  Future<void> _onLoad(FridgeLoadRequested e, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final r = await apiClient.get('/fridge/');
      final list = (r is Map ? (r['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      premiumGate?.reportReadSuccess();
      emit(FridgeLoaded(items: list));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onAdd(FridgeItemAdded e, Emitter<FridgeState> emit) async {
    try {
      final body = <String, dynamic>{
        'name': e.name,
        'quantity': e.quantity,
        'unit': e.unit,
        'expiry_date': e.expiryDate,
      };
      if (e.productId != null) body['product'] = e.productId;
      await apiClient.post('/fridge/', data: body);
      add(const FridgeLoadRequested());
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }

  Future<void> _onDelete(FridgeItemDeleted e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/${e.id}/');
      add(const FridgeLoadRequested());
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
DARTEOF
rm -f "$MOB/lib/features/fridge/bloc/fridge_state.dart" \
      "$MOB/lib/features/fridge/bloc/fridge_event.dart"
echo "  fridge_bloc.dart rewritten; legacy part files removed"

# =================================================================
echo
echo "===== [MOBILE 4/6] BarcodeScannerScreen ====="
mkdir -p "$MOB/lib/features/fridge/screens"
cat > "$MOB/lib/features/fridge/screens/barcode_scanner_screen.dart" <<'DARTEOF'
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class BarcodeScannerScreen extends StatefulWidget {
  const BarcodeScannerScreen({super.key});
  @override
  State<BarcodeScannerScreen> createState() => _BarcodeScannerScreenState();
}

class _BarcodeScannerScreenState extends State<BarcodeScannerScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    facing: CameraFacing.back,
  );
  bool _handled = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture cap) {
    if (_handled) return;
    final value = cap.barcodes.isNotEmpty ? cap.barcodes.first.rawValue : null;
    if (value == null || value.isEmpty) return;
    _handled = true;
    Navigator.of(context).pop(value);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Сканер штрих-кода'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () => _controller.toggleTorch(),
          ),
          IconButton(
            icon: const Icon(Icons.flip_camera_ios),
            onPressed: () => _controller.switchCamera(),
          ),
        ],
      ),
      body: Stack(
        children: [
          MobileScanner(controller: _controller, onDetect: _onDetect),
          Center(
            child: Container(
              width: 260,
              height: 260,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white.withOpacity(0.85), width: 3),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
          Positioned(
            left: 0, right: 0, bottom: 40,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.55),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  'Наведите камеру на штрих-код',
                  style: TextStyle(color: Colors.white, fontSize: 14),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
DARTEOF
echo "  barcode_scanner_screen.dart written"

# =================================================================
echo
echo "===== [MOBILE 5/6] AddFridgeItemSheet ====="
cat > "$MOB/lib/features/fridge/screens/add_fridge_item_sheet.dart" <<'DARTEOF'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'barcode_scanner_screen.dart';

const _UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

class AddFridgeItemSheet extends StatefulWidget {
  final ApiClient apiClient;
  const AddFridgeItemSheet({super.key, required this.apiClient});

  static Future<void> show(BuildContext context, ApiClient apiClient) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: BlocProvider.value(
          value: context.read<FridgeBloc>(),
          child: AddFridgeItemSheet(apiClient: apiClient),
        ),
      ),
    );
  }

  @override
  State<AddFridgeItemSheet> createState() => _AddFridgeItemSheetState();
}

class _AddFridgeItemSheetState extends State<AddFridgeItemSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _qtyCtrl = TextEditingController();
  String _unit = _UNITS.first;
  DateTime? _expiry;
  int? _productId;
  String? _imageUrl;
  bool _loadingBarcode = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _qtyCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _expiry ?? now.add(const Duration(days: 7)),
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365 * 3)),
    );
    if (picked != null) setState(() => _expiry = picked);
  }

  Future<void> _scanAndLookup() async {
    final scanned = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const BarcodeScannerScreen()),
    );
    if (scanned == null || scanned.isEmpty) return;
    setState(() {
      _loadingBarcode = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.post('/fridge/scan/', data: {'barcode': scanned});
      final m = (r is Map) ? Map<String, dynamic>.from(r) : <String, dynamic>{};
      setState(() {
        _nameCtrl.text = (m['name'] as String?) ?? scanned;
        _productId = m['id'] as int?;
        _imageUrl = m['image_url'] as String?;
        final du = (m['default_unit'] as String?) ?? '';
        if (du.isNotEmpty && _UNITS.contains(du)) _unit = du;
      });
    } catch (e) {
      final msg = e.toString();
      setState(() {
        _error = msg.contains('404') || msg.contains('not found')
            ? 'Штрих-код не найден. Заполните поля вручную.'
            : 'Ошибка поиска: $msg';
      });
    } finally {
      if (mounted) setState(() => _loadingBarcode = false);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    if (_expiry == null) {
      setState(() => _error = 'Укажите срок годности');
      return;
    }
    final qty = double.tryParse(_qtyCtrl.text.replaceAll(',', '.')) ?? 0;
    context.read<FridgeBloc>().add(FridgeItemAdded(
      name: _nameCtrl.text.trim(),
      quantity: qty,
      unit: _unit,
      expiryDate: DateFormat('yyyy-MM-dd').format(_expiry!),
      productId: _productId,
    ));
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 40, height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Row(
                children: [
                  const Text(
                    'Добавить в холодильник',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: _loadingBarcode ? null : _scanAndLookup,
                    icon: _loadingBarcode
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.qr_code_scanner),
                    tooltip: 'Сканировать штрих-код',
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (_imageUrl != null && _imageUrl!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.network(
                      _imageUrl!,
                      height: 120,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                    ),
                  ),
                ),
              TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Название *'),
                textInputAction: TextInputAction.next,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Обязательно' : null,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      controller: _qtyCtrl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Кол-во *'),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) return 'Обязательно';
                        final n = double.tryParse(v.replaceAll(',', '.'));
                        if (n == null || n <= 0) return 'Число > 0';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: DropdownButtonFormField<String>(
                      value: _unit,
                      decoration: const InputDecoration(labelText: 'Ед. изм. *'),
                      items: _UNITS
                          .map((u) => DropdownMenuItem(value: u, child: Text(u)))
                          .toList(),
                      onChanged: (v) => setState(() => _unit = v ?? _UNITS.first),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              InkWell(
                onTap: _pickDate,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Срок годности *',
                    suffixIcon: Icon(Icons.calendar_today),
                  ),
                  child: Text(
                    _expiry == null
                        ? 'Выбрать дату'
                        : DateFormat('dd.MM.yyyy').format(_expiry!),
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _submit,
                child: const Text('Добавить'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
DARTEOF
echo "  add_fridge_item_sheet.dart written"

# =================================================================
echo
echo "===== [MOBILE 6/6] FridgeScreen + router ====="
cat > "$MOB/lib/features/fridge/screens/fridge_screen.dart" <<'DARTEOF'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'add_fridge_item_sheet.dart';

class FridgeScreen extends StatefulWidget {
  final ApiClient apiClient;
  const FridgeScreen({super.key, required this.apiClient});

  @override
  State<FridgeScreen> createState() => _FridgeScreenState();
}

class _FridgeScreenState extends State<FridgeScreen> {
  @override
  void initState() {
    super.initState();
    context.read<FridgeBloc>().add(const FridgeLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Холодильник')),
      body: RefreshIndicator(
        onRefresh: () async => context.read<FridgeBloc>().add(const FridgeLoadRequested()),
        child: BlocBuilder<FridgeBloc, FridgeState>(
          builder: (context, state) {
            if (state is FridgeLoading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (state is FridgeError) {
              return ListView(children: [
                const SizedBox(height: 80),
                Center(child: Text(state.message)),
              ]);
            }
            final items = state is FridgeLoaded ? state.items : <Map<String, dynamic>>[];
            if (items.isEmpty) {
              return ListView(children: const [
                SizedBox(height: 100),
                Center(child: Text('Холодильник пуст\nНажмите + чтобы добавить', textAlign: TextAlign.center)),
              ]);
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final item = items[i];
                final expiry = item['expiry_date'] as String?;
                int? daysLeft;
                try {
                  if (expiry != null) {
                    daysLeft = DateTime.parse(expiry).difference(DateTime.now()).inDays;
                  }
                } catch (_) {}
                final imageUrl = item['product_image_url'] as String?;
                return ListTile(
                  leading: imageUrl != null && imageUrl.isNotEmpty
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: CachedNetworkImage(
                            imageUrl: imageUrl,
                            width: 40, height: 40, fit: BoxFit.cover,
                            errorWidget: (_, __, ___) => const Icon(Icons.inventory_2_outlined),
                          ),
                        )
                      : const Icon(Icons.inventory_2_outlined),
                  title: Text(item['name'] as String? ?? ''),
                  subtitle: daysLeft != null
                      ? Text(daysLeft < 0
                          ? 'Просрочено ${-daysLeft} дн.'
                          : 'Осталось дней: $daysLeft')
                      : null,
                  trailing: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                  onLongPress: () {
                    final id = item['id'];
                    if (id != null) {
                      context.read<FridgeBloc>().add(FridgeItemDeleted(id as int));
                    }
                  },
                );
              },
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => AddFridgeItemSheet.show(context, widget.apiClient),
        child: const Icon(Icons.add),
      ),
    );
  }
}
DARTEOF
echo "  fridge_screen.dart written"

python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/core/router/app_router.dart")
s = p.read_text()
old = "GoRoute(path: '/fridge',  builder: (_, __) => const FridgeScreen()),"
new = "GoRoute(path: '/fridge',  builder: (_, __) => FridgeScreen(apiClient: apiClient)),"
if old in s:
    p.write_text(s.replace(old, new))
    print("  app_router.dart: FridgeScreen now receives apiClient")
elif "FridgeScreen(apiClient: apiClient)" in s:
    print("  app_router.dart already updated")
else:
    print("WARN: marker not found in app_router.dart")
PYEOF

# =================================================================
echo
echo "===== [WEB 1/5] package.json: + @yudiel/react-qr-scanner ====="
python3 - <<'PYEOF'
import json
from pathlib import Path
p = Path("/opt/menugen/web/menugen-web/package.json")
data = json.loads(p.read_text())
deps = data.setdefault("dependencies", {})
if "@yudiel/react-qr-scanner" not in deps:
    deps["@yudiel/react-qr-scanner"] = "^2.3.0"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("  added @yudiel/react-qr-scanner")
else:
    print("  already present")
PYEOF

# =================================================================
echo
echo "===== [WEB 2/5] types: FridgeItem + Product ====="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/web/menugen-web/src/types/index.ts")
s = p.read_text()
if "interface FridgeItem" in s:
    print("  FridgeItem already present")
else:
    addition = '''
// ── Fridge ──────────────────────────────────────────────────────────────────
export interface Product {
  id: number;
  name: string;
  category?: string;
  default_unit?: string;
  calories_per_100g?: string | number | null;
  nutrition?: Record<string, number>;
  barcode?: string | null;
  image_url?: string | null;
}
export interface FridgeItem {
  id: number;
  product?: number | null;
  product_name?: string | null;
  product_category?: string | null;
  product_image_url?: string | null;
  name: string;
  quantity?: string | number | null;
  unit?: string;
  expiry_date?: string | null;
  created_at: string;
  updated_at: string;
}
export interface BarcodeLookupResult extends Product {
  source: 'local' | 'openfoodfacts';
}
'''
    p.write_text(s.rstrip() + "\n" + addition)
    print("  appended Product/FridgeItem/BarcodeLookupResult")
PYEOF

# =================================================================
echo
echo "===== [WEB 3/5] api/fridge.ts ====="
cat > "$WEB/src/api/fridge.ts" <<'TSEOF'
import client from './client';
import type {
  BarcodeLookupResult,
  FridgeItem,
  PaginatedResponse,
} from '../types';

export const fridgeApi = {
  list: () => client.get<PaginatedResponse<FridgeItem>>('/fridge/'),

  create: (data: {
    name: string;
    quantity: number;
    unit: string;
    expiry_date: string;
    product?: number | null;
  }) => client.post<FridgeItem>('/fridge/', data),

  delete: (id: number) => client.delete(`/fridge/${id}/`),

  scanBarcode: (barcode: string) =>
    client.post<BarcodeLookupResult>('/fridge/scan/', { barcode }),
};
TSEOF
echo "  fridge.ts written"

# =================================================================
echo
echo "===== [WEB 4/5] pages/Fridge/FridgePage + AddFridgeItemModal ====="
mkdir -p "$WEB/src/pages/Fridge" "$WEB/src/components/fridge"

cat > "$WEB/src/components/fridge/AddFridgeItemModal.tsx" <<'TSEOF'
import React, { useState, useRef } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { fridgeApi } from '../../api/fridge';
import type { BarcodeLookupResult, FridgeItem } from '../../types';

const UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

interface Props {
  onClose: () => void;
  onAdded: (item: FridgeItem) => void;
}

export const AddFridgeItemModal: React.FC<Props> = ({ onClose, onAdded }) => {
  const [name, setName]         = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit]         = useState(UNITS[0]);
  const [expiry, setExpiry]     = useState('');
  const [productId, setProductId] = useState<number | null>(null);
  const [imageUrl, setImageUrl]   = useState<string | null>(null);
  const [showScanner, setShowScanner] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const handledRef = useRef(false);

  const onBarcodeDetected = async (detected: { rawValue?: string }[]) => {
    if (handledRef.current) return;
    const code = detected[0]?.rawValue;
    if (!code) return;
    handledRef.current = true;
    setShowScanner(false);
    setScanLoading(true);
    setError(null);
    try {
      const { data } = await fridgeApi.scanBarcode(code);
      const p = data as BarcodeLookupResult;
      setName(p.name);
      setProductId(p.id);
      if (p.image_url) setImageUrl(p.image_url);
      if (p.default_unit && UNITS.includes(p.default_unit)) setUnit(p.default_unit);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        setError('Штрих-код не найден. Заполните поля вручную.');
        setName(`Штрих-код ${code}`);
      } else {
        setError('Ошибка поиска: ' + (e?.response?.data?.detail || e?.message || ''));
      }
    } finally {
      setScanLoading(false);
      handledRef.current = false;
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !quantity || !unit || !expiry) {
      setError('Заполните все обязательные поля');
      return;
    }
    const q = parseFloat(quantity.replace(',', '.'));
    if (!isFinite(q) || q <= 0) { setError('Кол-во должно быть > 0'); return; }
    setSubmitting(true);
    try {
      const { data } = await fridgeApi.create({
        name: name.trim(),
        quantity: q,
        unit,
        expiry_date: expiry,
        product: productId,
      });
      onAdded(data);
      onClose();
    } catch (e: any) {
      setError('Ошибка: ' + (e?.response?.data?.detail || e?.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-chocolate">Добавить в холодильник</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {showScanner ? (
            <div className="space-y-3">
              <div className="rounded-xl overflow-hidden border border-gray-200">
                <Scanner
                  onScan={onBarcodeDetected}
                  styles={{ container: { width: '100%' } }}
                  scanDelay={300}
                />
              </div>
              <Button variant="ghost" className="w-full" onClick={() => setShowScanner(false)}>
                Отмена
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  type="button"
                  className="flex-1"
                  onClick={() => { handledRef.current = false; setShowScanner(true); }}
                  disabled={scanLoading}
                >
                  {scanLoading ? 'Поиск...' : '📷 Сканировать штрих-код'}
                </Button>
              </div>

              {imageUrl && (
                <img src={imageUrl} alt="" className="max-h-32 mx-auto rounded-lg object-contain"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              )}

              <Input
                label="Название *"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />

              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Кол-во *"
                  type="number"
                  step="0.01"
                  min="0"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  required
                />
                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-chocolate">Ед. изм. *</label>
                  <select
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
                  >
                    {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
              </div>

              <Input
                label="Срок годности *"
                type="date"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
                required
              />

              {error && <p className="text-sm text-red-600">{error}</p>}

              <Button type="submit" className="w-full" loading={submitting}>
                Добавить
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
TSEOF
echo "  AddFridgeItemModal.tsx written"

cat > "$WEB/src/pages/Fridge/FridgePage.tsx" <<'TSEOF'
import React, { useEffect, useState, useCallback } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Card } from '../../components/ui/Card';
import { PageSpinner } from '../../components/ui/Spinner';
import { Button } from '../../components/ui/Button';
import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';
import type { FridgeItem } from '../../types';

function daysUntil(d: string | null | undefined): number | null {
  if (!d) return null;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((dt.getTime() - today.getTime()) / 86_400_000);
}

export const FridgePage: React.FC = () => {
  const [items, setItems]     = useState<FridgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await fridgeApi.list();
      setItems(data.results ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onAdded = (item: FridgeItem) => {
    setItems(prev => [item, ...prev]);
  };

  const onDelete = async (id: number) => {
    if (!window.confirm('Удалить продукт?')) return;
    await fridgeApi.delete(id);
    setItems(prev => prev.filter(it => it.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Холодильник</h1>
        <Button onClick={() => setShowAdd(true)}>+ Добавить</Button>
      </div>

      {loading ? <PageSpinner /> : items.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          Холодильник пуст. Нажмите «+ Добавить» чтобы внести продукт.
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map(it => {
            const dl = daysUntil(it.expiry_date);
            const dlColor = dl == null ? 'text-gray-500'
              : dl < 0 ? 'text-red-600'
              : dl < 3 ? 'text-yellow-600' : 'text-gray-600';
            return (
              <Card key={it.id} className="p-4 flex gap-3 items-start">
                {it.product_image_url ? (
                  <img src={it.product_image_url} alt=""
                    className="w-14 h-14 rounded-lg object-cover bg-gray-50"
                    onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                ) : (
                  <div className="w-14 h-14 rounded-lg bg-rice flex items-center justify-center text-2xl">📦</div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-chocolate truncate">{it.name}</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {it.quantity ?? ''} {it.unit ?? ''}
                  </p>
                  {it.expiry_date && (
                    <p className={`text-xs mt-1 ${dlColor}`}>
                      {dl != null && dl < 0
                        ? `Просрочено ${-dl} дн.`
                        : `Срок: ${it.expiry_date}${dl != null ? ` (через ${dl} дн)` : ''}`}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => onDelete(it.id)}
                  className="text-gray-400 hover:text-red-600 text-sm"
                  title="Удалить"
                >
                  🗑
                </button>
              </Card>
            );
          })}
        </div>
      )}

      {showAdd && (
        <AddFridgeItemModal
          onClose={() => setShowAdd(false)}
          onAdded={onAdded}
        />
      )}
    </div>
  );
};
TSEOF
echo "  FridgePage.tsx written"

# =================================================================
echo
echo "===== [WEB 5/5] App.tsx route + Sidebar nav ====="
python3 - <<'PYEOF'
from pathlib import Path

ap = Path("/opt/menugen/web/menugen-web/src/App.tsx")
s = ap.read_text()
import_line = "import { FridgePage }        from './pages/Fridge/FridgePage';"
if "FridgePage" not in s:
    s = s.replace(
        "import { DiaryPage }         from './pages/Diary/DiaryPage';",
        "import { DiaryPage }         from './pages/Diary/DiaryPage';\n" + import_line,
    )
    s = s.replace(
        '<Route path="diary"         element={<DiaryPage />} />',
        '<Route path="diary"         element={<DiaryPage />} />\n        '
        '<Route path="fridge"        element={<FridgePage />} />',
    )
    ap.write_text(s)
    print("  App.tsx: FridgePage route added")
else:
    print("  App.tsx already has FridgePage")

sb = Path("/opt/menugen/web/menugen-web/src/components/layout/Sidebar.tsx")
s = sb.read_text()
if "'/fridge'" in s or '"/fridge"' in s:
    print("  Sidebar already has /fridge")
else:
    s = s.replace(
        "{ path: '/diary',         icon: '📓', label: 'Дневник'      },",
        "{ path: '/diary',         icon: '📓', label: 'Дневник'      },\n"
        "  { path: '/fridge',        icon: '🧊', label: 'Холодильник'  },",
    )
    sb.write_text(s)
    print("  Sidebar: Холодильник link added")
PYEOF

echo
echo "===== DONE. Backup: $BAK ====="
