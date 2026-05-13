#!/usr/bin/env bash
# MG-606.C.2 fix — correct product-search URL in fridge gate test
# Location: /opt/menugen/backend/scripts/patch_606c2_fix_url.sh
# Run: bash /opt/menugen/backend/scripts/patch_606c2_fix_url.sh 2>&1 | tee /tmp/patch_606c2_fix_url.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"

TEST="${BACKEND}/apps/fridge/tests/test_mg_606c_premium_gate.py"

sed -i 's|/api/v1/fridge/products/|/api/v1/fridge/products/search/|g' "$TEST"
echo "✓ replaced /api/v1/fridge/products/ → /api/v1/fridge/products/search/"
grep -n "products" "$TEST"

echo
echo "===================================================================="
echo "Re-run MG-606.C fridge gate"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/fridge/tests/test_mg_606c_premium_gate.py -v --tb=short

echo
echo "===================================================================="
echo "Full fridge regression"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/fridge/ -v --tb=short

echo
echo "PATCH-606.C.2 fix-url — done"
