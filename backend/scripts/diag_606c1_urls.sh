#!/usr/bin/env bash
# DIAG: какие URL у menu (для теста deleted) + полный регресс menu
# Расположение: /opt/menugen/backend/scripts/diag_606c1_urls.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606c1_urls.sh 2>&1 | tee /tmp/diag_606c1_urls.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. menu/urls.py — все маршруты"
cat -n "${BACKEND}/apps/menu/urls.py"

hr "2. menu/tests — какие URL используются в тестах"
grep -rnE "reverse\(['\"][a-z_-]+['\"]\)" "${BACKEND}/apps/menu/tests/" | head -30

hr "3. menu/views.py — имена view классов (для понимания, какой view = какому URL)"
grep -nE "^class\s+\w+View" "${BACKEND}/apps/menu/views.py"

hr "4. Полный регресс menu (без обрезки) — может быть долго"
$COMPOSE exec -T backend pytest apps/menu/ -v --tb=short 2>&1 | tail -120

echo
echo "=== diag finished ==="
