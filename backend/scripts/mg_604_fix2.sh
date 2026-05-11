#!/usr/bin/env bash
# MG-604 fix-2: BoomDict должен быть непустым, иначе `nut or {}` его выкинет
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"

TEST="$BACKEND/apps/menu/tests/test_mg_604_portions.py"

echo "=========================================="
echo "  MG-604 FIX-2 portions.py"
echo "=========================================="

python3 <<PYEOF
import sys

PATH = "$TEST"
src = open(PATH).read()

old = '''        class BoomDict(dict):
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            nutrition = BoomDict()'''

new = '''        class BoomDict(dict):
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            # MG_604: непустой dict, чтобы `nut or {}` его не подменил
            nutrition = BoomDict({"x": 1})'''

if old not in src:
    print("ERR: блок не найден"); sys.exit(2)
src = src.replace(old, new)
open(PATH, "w").write(src)
print("OK: BoomDict({'x': 1})")
PYEOF

$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/tests/test_mg_604_portions.py').read()); print('AST OK')"

echo
echo "--- coverage report ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing | grep -E "portions|TOTAL"
'

echo "=========================================="
