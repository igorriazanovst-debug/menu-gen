#!/usr/bin/env bash
# DIAG: где находится test_mg_606b_premium_or_readonly.py?
# Расположение: /opt/menugen/backend/scripts/diag_606b_locate.sh
set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. Поиск test_mg_606b на хосте"
find "$ROOT/backend" -name "test_mg_606b*" 2>/dev/null

hr "2. ls apps/diary/tests/ на хосте"
ls -la "$ROOT/backend/apps/diary/tests/" | grep -vE '__pycache__|\.pyc$'

hr "3. ls apps/diary/tests/ внутри контейнера"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend ls -la apps/diary/tests/ | grep -vE '__pycache__|\.pyc$'

hr "4. Содержимое volume mapping (docker-compose.yml backend volumes)"
grep -A 20 "backend:" "$ROOT/docker-compose.yml" | head -40

hr "5. pwd внутри контейнера + sanity"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend bash -c "pwd && ls apps/diary/tests/test_mg_606b* 2>/dev/null || echo '  FILE NOT IN CONTAINER'"

echo
echo "=== diag finished ==="
