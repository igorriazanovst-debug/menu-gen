#!/usr/bin/env bash
# MG-602 fix: расширить except в _recipe_calories до AttributeError
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"
TS=$(date +%Y%m%d_%H%M%S)

VIEWS="$BACKEND/apps/menu/views.py"

echo "=========================================="
echo "  MG-602 FIX recipe_calories  ($TS)"
echo "=========================================="

cp "$VIEWS" "$VIEWS.bak.${TS}"
echo "Backup: $VIEWS.bak.${TS}"

python3 <<PYEOF
import sys

VIEWS = "$VIEWS"
src = open(VIEWS).read()

old = '''def _recipe_calories(recipe):
    try:
        return float(recipe.nutrition.get("calories", {}).get("value", 0) or 0)
    except (TypeError, ValueError):
        return 0.0'''

new = '''def _recipe_calories(recipe):
    # MG_602_V_views: добавлен AttributeError для случая, когда nutrition['calories'] не dict
    try:
        return float(recipe.nutrition.get("calories", {}).get("value", 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0'''

if old not in src:
    print("ERR: блок _recipe_calories не найден"); sys.exit(2)
src = src.replace(old, new)
open(VIEWS, "w").write(src)
print("OK: _recipe_calories пропатчен")
PYEOF

$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/views.py').read()); print('apps/menu/views.py: AST OK')"

echo
echo "--- pytest test_mg_602_views.py ---"
$COMPOSE exec -T backend pytest apps/menu/tests/test_mg_602_views.py -v --tb=short 2>&1 | tail -20

echo
echo "--- coverage report ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing
'

echo
echo "=========================================="
echo "  MG-602 FIX DONE"
echo "=========================================="
