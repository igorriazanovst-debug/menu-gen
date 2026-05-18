#!/usr/bin/env bash
# Fridge item detail card
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
MOB="$ROOT/mobile/menugen_app"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
cd "$ROOT"

TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/fridge_detail_${TS}"
mkdir -p "$BAK/backend/fridge" "$BAK/mobile" "$BAK/web"

echo "===== [BACKUP] ====="
cp "$BACKEND/apps/fridge/views.py" "$BAK/backend/fridge/"
cp "$BACKEND/apps/fridge/urls.py"  "$BAK/backend/fridge/"
cp "$MOB/lib/features/fridge/screens/fridge_screen.dart" "$BAK/mobile/"
cp "$WEB/src/pages/Fridge/FridgePage.tsx" "$BAK/web/"
echo "Backup -> $BAK"

# =================================================================
echo
echo "===== [BACKEND 1/3] Add usage_in_menus service + detail view ====="
cat > "$BACKEND/apps/fridge/services.py" <<'PYEOF'
"""Fridge services: OpenFoodFacts lookup + menu-usage stats."""
from __future__ import annotations

import datetime
import logging
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from apps.menu.models import MenuItem

from .models import Product

logger = logging.getLogger(__name__)


# ── OpenFoodFacts (existing) ────────────────────────────────────────────────
def _normalize_off_product(raw: dict) -> Optional[dict]:
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

    product, _ = Product.objects.update_or_create(barcode=barcode, defaults=fields)
    return product


# ── Menu usage stats ────────────────────────────────────────────────────────
def get_menu_usage_30d(family, product_name: str, days: int = 30) -> dict:
    """
    Count occurrences of a product in menu items for the given family.
    Match: case-insensitive exact match of ingredient.name == product_name.
    Period: Menu.start_date in [today - days, today].
    Returns: {"count": int, "recipes": [{"recipe_id", "title", "times"}], "period_days": days}
    """
    if not family or not product_name:
        return {"count": 0, "recipes": [], "period_days": days}

    target = product_name.strip().lower()
    if not target:
        return {"count": 0, "recipes": [], "period_days": days}

    today = timezone.now().date()
    since = today - datetime.timedelta(days=days)

    qs = (
        MenuItem.objects
        .filter(
            menu__family=family,
            menu__start_date__gte=since,
            menu__start_date__lte=today,
        )
        .select_related("recipe")
    )

    total = 0
    by_recipe: dict[int, dict] = {}
    for item in qs.iterator():
        recipe = item.recipe
        ingredients = recipe.ingredients or []
        if not isinstance(ingredients, list):
            continue
        match = False
        for ing in ingredients:
            if isinstance(ing, dict):
                nm = (ing.get("name") or "").strip().lower()
                if nm == target:
                    match = True
                    break
        if match:
            total += 1
            slot = by_recipe.get(recipe.id)
            if slot is None:
                by_recipe[recipe.id] = {
                    "recipe_id": recipe.id,
                    "title": recipe.title,
                    "times": 1,
                }
            else:
                slot["times"] += 1

    top = sorted(by_recipe.values(), key=lambda x: x["times"], reverse=True)[:10]
    return {"count": total, "recipes": top, "period_days": days}
PYEOF
echo "  services.py written"

# patch views: add FridgeItemDetailsView
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/fridge/views.py")
s = p.read_text()
if "class FridgeItemDetailsView" in s:
    print("  FridgeItemDetailsView already present")
else:
    addition = '''

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
            import datetime as _dt
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
'''
    # Inject before ProductSearchView
    marker = "class ProductSearchView(generics.ListAPIView):"
    if marker not in s:
        raise SystemExit("ERROR: marker not found in views.py")
    p.write_text(s.replace(marker, addition.lstrip() + "\n\n" + marker))
    print("  FridgeItemDetailsView appended")
PYEOF

# patch urls
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/fridge/urls.py")
s = p.read_text()
if "fridge-item-details" in s:
    print("  url already present")
else:
    # add import
    s = s.replace(
        "from .views import BarcodeLookupView, FridgeItemDetailView, FridgeListCreateView, ProductSearchView",
        "from .views import (\n"
        "    BarcodeLookupView,\n"
        "    FridgeItemDetailView,\n"
        "    FridgeItemDetailsView,\n"
        "    FridgeListCreateView,\n"
        "    ProductSearchView,\n"
        ")",
    )
    # add route after fridge-item-detail
    s = s.replace(
        'path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),',
        'path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),\n'
        '    path("<int:pk>/details/", FridgeItemDetailsView.as_view(), name="fridge-item-details"),',
    )
    p.write_text(s)
    print("  urls.py updated")
PYEOF

# =================================================================
echo
echo "===== [BACKEND 2/3] Tests ====="
cat > "$BACKEND/apps/fridge/tests/test_fridge_item_details.py" <<'PYEOF'
"""Tests for GET /fridge/<id>/details/ — nutrition, days_left, usage_30d."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
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
    Subscription.objects.create(
        family=family, plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user, family


def _auth(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
def test_details_product_null_returns_dashes():
    user, family = _family_with_premium()
    item = FridgeItem.objects.create(
        family=family, name="Молоко", quantity=1, unit="л",
        expiry_date=timezone.now().date() + datetime.timedelta(days=5),
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200, resp.content
    assert resp.data["item"]["name"] == "Молоко"
    assert resp.data["product"] is None
    assert resp.data["days_left"] == 5
    assert resp.data["usage_30d"]["count"] == 0


@pytest.mark.django_db
def test_details_with_product_nutrition_and_image():
    user, family = _family_with_premium()
    p = Product.objects.create(
        name="Молоко", barcode="111",
        calories_per_100g=Decimal("60"),
        nutrition={"proteins": 3, "fats": 2.5, "carbs": 4.7},
        image_url="https://example.org/milk.jpg",
    )
    item = FridgeItem.objects.create(
        family=family, product=p, name="Молоко",
        quantity=Decimal("1"), unit="л",
        expiry_date=timezone.now().date() + datetime.timedelta(days=3),
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200
    pd = resp.data["product"]
    assert pd is not None
    assert pd["image_url"] == "https://example.org/milk.jpg"
    assert pd["nutrition"]["proteins"] == 3
    assert resp.data["days_left"] == 3


@pytest.mark.django_db
def test_details_usage_30d_counts_exact_name():
    user, family = _family_with_premium()
    today = timezone.now().date()

    # Recipe that uses 'Молоко'
    recipe_milk = Recipe.objects.create(
        title="Каша",
        ingredients=[{"name": "Молоко", "quantity": "200", "unit": "мл"}],
        steps=[{"text": "Варить"}],
    )
    # Recipe with different name (should NOT match)
    recipe_other = Recipe.objects.create(
        title="Салат",
        ingredients=[{"name": "Огурец"}],
        steps=[],
    )
    # Recipe with 'молоко' lowercase — should MATCH (case-insensitive)
    recipe_milk2 = Recipe.objects.create(
        title="Блины",
        ingredients=[{"name": "молоко"}],
        steps=[],
    )

    # Menu within last 30 days
    menu_inside = Menu.objects.create(
        family=family, creator_id=user.id, period_days=7,
        start_date=today - datetime.timedelta(days=5),
        end_date=today + datetime.timedelta(days=2),
        status="active",
    )
    MenuItem.objects.create(menu=menu_inside, recipe=recipe_milk, meal_type="breakfast",
                            meal_slot="breakfast", day_offset=0)
    MenuItem.objects.create(menu=menu_inside, recipe=recipe_milk2, meal_type="lunch",
                            meal_slot="lunch", day_offset=1, component_role="grain")
    MenuItem.objects.create(menu=menu_inside, recipe=recipe_other, meal_type="dinner",
                            meal_slot="dinner", day_offset=2, component_role="vegetable")

    # Menu OUTSIDE 30-day window — should NOT count
    menu_outside = Menu.objects.create(
        family=family, creator_id=user.id, period_days=7,
        start_date=today - datetime.timedelta(days=60),
        end_date=today - datetime.timedelta(days=53),
        status="archived",
    )
    MenuItem.objects.create(menu=menu_outside, recipe=recipe_milk, meal_type="breakfast",
                            meal_slot="breakfast", day_offset=0)

    item = FridgeItem.objects.create(
        family=family, name="Молоко", quantity=1, unit="л",
        added_by_id=user.id,
    )
    c = _auth(user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 200
    usage = resp.data["usage_30d"]
    # 2 matches inside the window: recipe_milk + recipe_milk2 (case-insensitive)
    assert usage["count"] == 2, usage
    assert usage["period_days"] == 30
    titles = {r["title"] for r in usage["recipes"]}
    assert titles == {"Каша", "Блины"}, titles


@pytest.mark.django_db
def test_details_404_for_other_family_item():
    _, family_a = _family_with_premium()
    item = FridgeItem.objects.create(
        family=family_a, name="X", quantity=1, unit="шт",
    )
    # different user
    other_user = User.objects.create_user(email="o@o.o", password="x", name="O")
    other_family = Family.objects.create(name="OF", owner=other_user)
    FamilyMember.objects.create(family=other_family, user=other_user, role="head")
    plan = SubscriptionPlan.objects.get(code="premium")
    Subscription.objects.create(
        family=other_family, plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )

    c = _auth(other_user)
    resp = c.get(reverse("fridge-item-details", kwargs={"pk": item.id}))
    assert resp.status_code == 404
PYEOF
echo "  test_fridge_item_details.py written"

echo
echo "  running tests..."
$COMPOSE exec -T backend pytest apps/fridge/tests/test_fridge_item_details.py -v --tb=short 2>&1 | tail -30

echo
echo "===== [BACKEND 3/3] Full fridge regression ====="
$COMPOSE exec -T backend pytest apps/fridge/ --tb=short 2>&1 | tail -15

# =================================================================
echo
echo "===== [MOBILE 1/2] FridgeItemDetailScreen ====="
cat > "$MOB/lib/features/fridge/screens/fridge_item_detail_screen.dart" <<'DARTEOF'
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';

class FridgeItemDetailScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int itemId;
  const FridgeItemDetailScreen({super.key, required this.apiClient, required this.itemId});

  @override
  State<FridgeItemDetailScreen> createState() => _FridgeItemDetailScreenState();
}

class _FridgeItemDetailScreenState extends State<FridgeItemDetailScreen> {
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final r = await widget.apiClient.get('/fridge/${widget.itemId}/details/');
      setState(() {
        _data = (r is Map) ? Map<String, dynamic>.from(r) : null;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Карточка продукта')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final data = _data ?? {};
    final item = (data['item'] as Map?)?.cast<String, dynamic>() ?? {};
    final product = (data['product'] as Map?)?.cast<String, dynamic>();
    final daysLeft = data['days_left'] as int?;
    final usage = (data['usage_30d'] as Map?)?.cast<String, dynamic>() ?? {};

    final name = (item['name'] as String?) ?? '';
    final qty = item['quantity'];
    final unit = (item['unit'] as String?) ?? '';
    final expiry = item['expiry_date'] as String?;
    final imageUrl = (item['product_image_url'] as String?)
        ?? (product?['image_url'] as String?);

    // nutrition: product.nutrition + calories_per_100g
    final nutrition = (product?['nutrition'] as Map?)?.cast<String, dynamic>() ?? {};
    final kcal = product?['calories_per_100g'];

    final usageCount = (usage['count'] as int?) ?? 0;
    final recipes = (usage['recipes'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Header: image + name
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (imageUrl != null && imageUrl.isNotEmpty)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: CachedNetworkImage(
                  imageUrl: imageUrl,
                  width: 96, height: 96, fit: BoxFit.cover,
                  errorWidget: (_, __, ___) => Container(
                    width: 96, height: 96,
                    color: Colors.grey.shade100,
                    child: const Icon(Icons.image_not_supported_outlined, size: 40),
                  ),
                ),
              )
            else
              Container(
                width: 96, height: 96,
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.inventory_2_outlined, size: 40),
              ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  if (product?['category'] != null && (product!['category'] as String).isNotEmpty)
                    Text(product['category'] as String,
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                ],
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Stock + expiry
        Row(
          children: [
            Expanded(
              child: _statCard(
                icon: Icons.scale,
                label: 'Остаток',
                value: '${qty ?? '—'} $unit',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _statCard(
                icon: Icons.event,
                label: 'Срок годности',
                value: daysLeft == null
                    ? '—'
                    : daysLeft < 0
                        ? 'Просрочено\n${-daysLeft} дн.'
                        : '$daysLeft дн.',
                color: daysLeft == null
                    ? null
                    : daysLeft < 0
                        ? Colors.red
                        : daysLeft < 3
                            ? Colors.orange
                            : null,
              ),
            ),
          ],
        ),

        if (expiry != null) Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text('Годен до $expiry',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
              textAlign: TextAlign.center),
        ),

        const SizedBox(height: 24),

        // KBJU
        const Text('Пищевая ценность (на 100 г)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (product == null)
          const Text('— нет данных',
              style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic))
        else
          Wrap(
            spacing: 8, runSpacing: 8,
            children: [
              _kbjuChip('Ккал', kcal),
              _kbjuChip('Белки', nutrition['proteins']),
              _kbjuChip('Жиры', nutrition['fats']),
              _kbjuChip('Углеводы', nutrition['carbs']),
              if (nutrition['fiber'] != null) _kbjuChip('Клетч.', nutrition['fiber']),
            ],
          ),

        const SizedBox(height: 24),

        // Usage in menu
        Row(
          children: [
            const Text('Использование в меню',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: usageCount > 0 ? Colors.green.shade50 : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text('за 30 дн: $usageCount',
                  style: TextStyle(
                    fontSize: 12,
                    color: usageCount > 0 ? Colors.green.shade800 : Colors.grey.shade700,
                  )),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (recipes.isEmpty)
          const Text('Этот продукт не появлялся в меню за последние 30 дней.',
              style: TextStyle(color: Colors.grey, fontSize: 13))
        else
          Column(
            children: recipes.map((r) {
              final m = (r as Map).cast<String, dynamic>();
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.restaurant_menu),
                title: Text(m['title'] as String? ?? ''),
                trailing: Text('×${m['times']}',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                onTap: () {
                  final id = m['recipe_id'];
                  if (id != null) context.go('/recipes/$id');
                },
              );
            }).toList(),
          ),
      ],
    );
  }

  Widget _statCard({
    required IconData icon,
    required String label,
    required String value,
    Color? color,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: color ?? Colors.grey.shade600),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: color)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _kbjuChip(String label, dynamic value) {
    final txt = value == null
        ? '—'
        : value is num
            ? value.toStringAsFixed(value % 1 == 0 ? 0 : 1)
            : value.toString();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text('$label: $txt', style: const TextStyle(fontSize: 13)),
    );
  }
}
DARTEOF
echo "  fridge_item_detail_screen.dart written"

# patch router: add /fridge/:id/details route
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/core/router/app_router.dart")
s = p.read_text()
if "FridgeItemDetailScreen" in s:
    print("  router already has FridgeItemDetailScreen")
else:
    s = s.replace(
        "import '../../features/fridge/screens/fridge_screen.dart';",
        "import '../../features/fridge/screens/fridge_screen.dart';\n"
        "import '../../features/fridge/screens/fridge_item_detail_screen.dart';",
    )
    # Add as top-level route (outside ShellRoute so it gets a full screen)
    marker = "GoRoute(\n          path: '/recipes/:id',"
    addition = (
        "GoRoute(\n"
        "          path: '/fridge/:id/details',\n"
        "          builder: (_, state) => FridgeItemDetailScreen(\n"
        "            apiClient: apiClient,\n"
        "            itemId: int.parse(state.pathParameters['id']!),\n"
        "          ),\n"
        "        ),\n"
        "        " + marker
    )
    if marker not in s:
        raise SystemExit("ERROR: '/recipes/:id' marker not found")
    p.write_text(s.replace(marker, addition))
    print("  app_router.dart: /fridge/:id/details route added")
PYEOF

# patch fridge_screen.dart: ListTile onTap → navigate
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/mobile/menugen_app/lib/features/fridge/screens/fridge_screen.dart")
s = p.read_text()

# 1. Add go_router import
if "import 'package:go_router/go_router.dart';" not in s:
    s = s.replace(
        "import 'package:cached_network_image/cached_network_image.dart';",
        "import 'package:cached_network_image/cached_network_image.dart';\n"
        "import 'package:go_router/go_router.dart';",
    )

# 2. Add onTap to ListTile (before onLongPress)
old = """trailing: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                  onLongPress: () {"""
new = """trailing: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                  onTap: () {
                    final id = item['id'];
                    if (id != null) context.push('/fridge/$id/details');
                  },
                  onLongPress: () {"""
if old in s:
    s = s.replace(old, new)
    print("  fridge_screen.dart: onTap → details added")
elif "onTap: () {" in s and "/fridge/" in s:
    print("  fridge_screen.dart: onTap already wired")
else:
    raise SystemExit("ERROR: ListTile trailing/onLongPress marker not found in fridge_screen.dart")

Path("/opt/menugen/mobile/menugen_app/lib/features/fridge/screens/fridge_screen.dart").write_text(s)
PYEOF

# =================================================================
echo
echo "===== [WEB 1/2] api/fridge.ts: + details() ====="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/web/menugen-web/src/api/fridge.ts")
s = p.read_text()
if "details:" in s:
    print("  details() already present")
else:
    s = s.replace(
        "  scanBarcode: (barcode: string) =>",
        "  details: (id: number) => client.get<FridgeItemDetailsResponse>(`/fridge/${id}/details/`),\n\n"
        "  scanBarcode: (barcode: string) =>",
    )
    # add type import
    s = s.replace(
        "import type {\n  BarcodeLookupResult,\n  FridgeItem,\n  PaginatedResponse,\n} from '../types';",
        "import type {\n"
        "  BarcodeLookupResult,\n"
        "  FridgeItem,\n"
        "  FridgeItemDetailsResponse,\n"
        "  PaginatedResponse,\n"
        "} from '../types';",
    )
    p.write_text(s)
    print("  api/fridge.ts updated")
PYEOF

# types
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/web/menugen-web/src/types/index.ts")
s = p.read_text()
if "FridgeItemDetailsResponse" in s:
    print("  type already present")
else:
    addition = '''
export interface FridgeMenuUsageRecipe {
  recipe_id: number;
  title: string;
  times: number;
}
export interface FridgeMenuUsage {
  count: number;
  period_days: number;
  recipes: FridgeMenuUsageRecipe[];
}
export interface FridgeItemDetailsResponse {
  item: FridgeItem;
  product: Product | null;
  days_left: number | null;
  usage_30d: FridgeMenuUsage;
}
'''
    p.write_text(s.rstrip() + "\n" + addition)
    print("  types/index.ts updated")
PYEOF

# =================================================================
echo
echo "===== [WEB 2/2] FridgeItemDetailModal + wire click on card ====="
cat > "$WEB/src/components/fridge/FridgeItemDetailModal.tsx" <<'TSEOF'
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fridgeApi } from '../../api/fridge';
import { Spinner } from '../ui/Spinner';
import type { FridgeItemDetailsResponse } from '../../types';

interface Props {
  itemId: number;
  onClose: () => void;
}

const fmtNum = (v: any): string => {
  if (v == null) return '—';
  if (typeof v === 'number') return v % 1 === 0 ? String(v) : v.toFixed(1);
  return String(v);
};

export const FridgeItemDetailModal: React.FC<Props> = ({ itemId, onClose }) => {
  const [data, setData] = useState<FridgeItemDetailsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { data } = await fridgeApi.details(itemId);
        if (!cancelled) setData(data);
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || e?.message || 'Ошибка');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [itemId]);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-bold text-chocolate">Карточка продукта</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {loading && <div className="flex justify-center py-8"><Spinner size="lg" /></div>}
          {error && <p className="text-red-600">{error}</p>}

          {data && (() => {
            const { item, product, days_left, usage_30d } = data;
            const imageUrl = item.product_image_url || product?.image_url;
            const nutrition = product?.nutrition || {};
            const daysColor =
              days_left == null ? 'text-gray-500'
              : days_left < 0 ? 'text-red-600'
              : days_left < 3 ? 'text-yellow-600' : 'text-green-700';

            return (
              <div className="space-y-5">
                {/* Header */}
                <div className="flex gap-4">
                  {imageUrl ? (
                    <img src={imageUrl} alt="" className="w-24 h-24 rounded-xl object-cover bg-gray-50"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                  ) : (
                    <div className="w-24 h-24 rounded-xl bg-rice flex items-center justify-center text-4xl">📦</div>
                  )}
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-chocolate">{item.name}</h3>
                    {product?.category && (
                      <p className="text-sm text-gray-500 mt-1">{product.category}</p>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-500">Остаток</p>
                    <p className="font-semibold text-chocolate">
                      {item.quantity ?? '—'} {item.unit ?? ''}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-500">Срок годности</p>
                    <p className={`font-semibold ${daysColor}`}>
                      {days_left == null ? '—'
                        : days_left < 0 ? `Просрочено ${-days_left} дн.`
                        : `${days_left} дн.`}
                    </p>
                    {item.expiry_date && (
                      <p className="text-xs text-gray-400 mt-0.5">до {item.expiry_date}</p>
                    )}
                  </div>
                </div>

                {/* KBJU */}
                <div>
                  <h4 className="font-semibold mb-2 text-chocolate">Пищевая ценность (на 100 г)</h4>
                  {!product ? (
                    <p className="text-sm text-gray-400 italic">— нет данных</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Ккал: <b>{fmtNum(product.calories_per_100g)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Белки: <b>{fmtNum(nutrition.proteins)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Жиры: <b>{fmtNum(nutrition.fats)}</b>
                      </span>
                      <span className="px-3 py-1 bg-rice rounded-full text-sm">
                        Углеводы: <b>{fmtNum(nutrition.carbs)}</b>
                      </span>
                      {nutrition.fiber != null && (
                        <span className="px-3 py-1 bg-rice rounded-full text-sm">
                          Клетч.: <b>{fmtNum(nutrition.fiber)}</b>
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Usage */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="font-semibold text-chocolate">Использование в меню</h4>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      usage_30d.count > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      за 30 дн: {usage_30d.count}
                    </span>
                  </div>
                  {usage_30d.recipes.length === 0 ? (
                    <p className="text-sm text-gray-400 italic">
                      Этот продукт не появлялся в меню за последние 30 дней.
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {usage_30d.recipes.map(r => (
                        <li key={r.recipe_id}
                            className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                            onClick={() => { onClose(); navigate(`/recipes?id=${r.recipe_id}`); }}>
                          <span className="text-sm">🍽 {r.title}</span>
                          <span className="text-sm font-semibold text-tomato">×{r.times}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};
TSEOF
echo "  FridgeItemDetailModal.tsx written"

# patch FridgePage: open modal on card click
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/web/menugen-web/src/pages/Fridge/FridgePage.tsx")
s = p.read_text()
if "FridgeItemDetailModal" in s:
    print("  FridgePage already wired")
else:
    s = s.replace(
        "import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';",
        "import { AddFridgeItemModal } from '../../components/fridge/AddFridgeItemModal';\n"
        "import { FridgeItemDetailModal } from '../../components/fridge/FridgeItemDetailModal';",
    )
    s = s.replace(
        "const [showAdd, setShowAdd] = useState(false);",
        "const [showAdd, setShowAdd] = useState(false);\n"
        "  const [detailId, setDetailId] = useState<number | null>(null);",
    )
    s = s.replace(
        '<Card key={it.id} className="p-4 flex gap-3 items-start">',
        '<Card key={it.id} className="p-4 flex gap-3 items-start cursor-pointer hover:shadow-md transition" onClick={() => setDetailId(it.id)}>',
    )
    # prevent delete click from triggering card click
    s = s.replace(
        'onClick={() => onDelete(it.id)}',
        'onClick={(e) => { e.stopPropagation(); onDelete(it.id); }}',
    )
    s = s.replace(
        "{showAdd && (\n        <AddFridgeItemModal",
        "{detailId != null && (\n"
        "        <FridgeItemDetailModal\n"
        "          itemId={detailId}\n"
        "          onClose={() => setDetailId(null)}\n"
        "        />\n"
        "      )}\n\n"
        "      {showAdd && (\n"
        "        <AddFridgeItemModal",
    )
    p.write_text(s)
    print("  FridgePage.tsx wired to detail modal")
PYEOF

echo
echo "===== DONE. Backup: $BAK ====="
