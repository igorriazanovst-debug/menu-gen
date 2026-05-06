#!/bin/bash
set -euo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
F="$ROOT/backend/apps/menu/generator.py"
TS="$(date +%Y%m%d_%H%M%S)"
cp -v "$F" "/tmp/mg_304_v4_backup_${TS}_generator.py"

sed -i 's/self\._allowed_for_member(r, hard_exclude)/self._recipe_passes_hard(r, hard_exclude)/g' "$F"

echo
echo "=== verify ==="
grep -nE "_allowed_for_member|_recipe_passes_hard" "$F" | head -20

echo
echo "=== compile ==="
docker compose -f "$COMPOSE" exec -T backend python -c "import py_compile; py_compile.compile('/app/apps/menu/generator.py', doraise=True); print('OK')"

echo
echo "=== pytest MG-304 + MG-301 ==="
docker compose -f "$COMPOSE" exec -T backend pytest \
  apps/menu/tests/test_mg_301.py \
  apps/menu/tests/test_mg_304.py -q 2>&1 | tail -25
