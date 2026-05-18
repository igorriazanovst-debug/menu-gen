#!/usr/bin/env bash
# Continue fridge add-item patch (after settings path fix)
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
MOB="$ROOT/mobile/menugen_app"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
cd "$ROOT"

# =================================================================
echo "===== [BACKEND 1/5 FIX] Settings: OPENFOODFACTS_* ====="
SETTINGS="$BACKEND/config/settings.py"
echo "Settings file: $SETTINGS"
if ! grep -q "OPENFOODFACTS_BASE_URL" "$SETTINGS"; then
  cat >> "$SETTINGS" <<'PYEOF'

# ── Fridge: OpenFoodFacts fallback for unknown barcodes ──────────────
OPENFOODFACTS_BASE_URL = os.environ.get(
    "OPENFOODFACTS_BASE_URL",
    "https://world.openfoodfacts.org",
)
OPENFOODFACTS_TIMEOUT = float(os.environ.get("OPENFOODFACTS_TIMEOUT", "4.0"))
OPENFOODFACTS_USER_AGENT = os.environ.get(
    "OPENFOODFACTS_USER_AGENT",
    "MenuGen/1.0 (+https://menugen.local)",
)
PYEOF
  echo "  appended OPENFOODFACTS_* to $SETTINGS"
else
  echo "  already present"
fi

# Verify settings has 'import os'
if ! grep -qE "^import os" "$SETTINGS"; then
  echo "WARN: 'import os' not at top of settings.py. Showing top 5 lines:"
  head -5 "$SETTINGS"
fi

# =================================================================
echo
echo "===== [BACKEND 2/5] Verify model and generate migration ====="
grep -n "image_url" "$BACKEND/apps/fridge/models.py" || echo "ERROR: image_url not in models"

echo "  generating migration..."
$COMPOSE exec -T backend python manage.py makemigrations fridge --name product_image_url 2>&1 | tail -5

echo "  applying migration..."
$COMPOSE exec -T backend python manage.py migrate fridge 2>&1 | tail -5

# =================================================================
echo
echo "===== [BACKEND 3/5] Verify serializers + views + services already written ====="
grep -l "image_url" "$BACKEND/apps/fridge/serializers.py" && echo "  serializers: OK" || echo "  serializers: MISSING"
grep -l "fetch_product_from_off" "$BACKEND/apps/fridge/views.py" && echo "  views: OK" || echo "  views: MISSING"
[ -f "$BACKEND/apps/fridge/services.py" ] && echo "  services.py: OK" || echo "  services.py: MISSING"

# =================================================================
echo
echo "===== [BACKEND 4/5] Tests already written - run them ====="
[ -f "$BACKEND/apps/fridge/tests/test_barcode_off_fallback.py" ] && echo "  test file: OK" || echo "  test file: MISSING"

$COMPOSE exec -T backend pytest apps/fridge/tests/test_barcode_off_fallback.py -v --tb=short 2>&1 | tail -40

# =================================================================
echo
echo "===== [BACKEND 5/5] Regression: full fridge tests ====="
$COMPOSE exec -T backend pytest apps/fridge/ --tb=short 2>&1 | tail -15

# =================================================================
echo
echo "===== [VERIFY] Mobile + Web files (from previous run) ====="
echo "--- pubspec.yaml fridge-related:"
grep -E "mobile_scanner|image_picker|permission_handler" "$MOB/pubspec.yaml" || echo "  MISSING"
echo "--- Manifest CAMERA:"
grep "android.permission.CAMERA" "$MOB/android/app/src/main/AndroidManifest.xml" || echo "  MISSING"
echo "--- fridge mobile files:"
ls -la "$MOB/lib/features/fridge/screens/"
ls -la "$MOB/lib/features/fridge/bloc/"
echo "--- web fridge files:"
ls "$WEB/src/api/fridge.ts" 2>/dev/null && echo "  fridge.ts: OK" || echo "  fridge.ts: MISSING"
ls "$WEB/src/pages/Fridge/FridgePage.tsx" 2>/dev/null && echo "  FridgePage: OK" || echo "  MISSING"
ls "$WEB/src/components/fridge/AddFridgeItemModal.tsx" 2>/dev/null && echo "  AddFridgeItemModal: OK" || echo "  MISSING"
grep -q "FridgePage" "$WEB/src/App.tsx" && echo "  App.tsx route: OK" || echo "  App.tsx route: MISSING"
grep -q "/fridge" "$WEB/src/components/layout/Sidebar.tsx" && echo "  Sidebar: OK" || echo "  Sidebar: MISSING"
grep -q "@yudiel/react-qr-scanner" "$WEB/package.json" && echo "  package.json dep: OK" || echo "  dep: MISSING"

echo
echo "===== DONE ====="
