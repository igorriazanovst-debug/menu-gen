#!/usr/bin/env bash
# MG-606.C.1 fix: исправить URL в test_deleted_list (quarantine, не deleted)
# Расположение: /opt/menugen/backend/scripts/patch_606c1_fix_url.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606c1_fix_url.sh 2>&1 | tee /tmp/patch_606c1_fix_url.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

TEST="${BACKEND}/apps/menu/tests/test_mg_606c_premium_gate.py"

BAKDIR="${ROOT}/backups/606c1_fix_url_${TS}"
mkdir -p "$BAKDIR"
cp "$TEST" "$BAKDIR/test_mg_606c_premium_gate.py.bak"

# Заменить /api/v1/menu/deleted/ на /api/v1/menu/quarantine/
sed -i 's|/api/v1/menu/deleted/|/api/v1/menu/quarantine/|g' "$TEST"

echo "✓ заменено /api/v1/menu/deleted/ → /api/v1/menu/quarantine/"
grep -n "quarantine\|deleted" "$TEST" || true

# Прогон только MG-606.C
echo
echo "===================================================================="
echo "Прогон MG-606.C"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/menu/tests/test_mg_606c_premium_gate.py -v --tb=short

echo
echo "PATCH-606.C.1 fix-url — финиш"
