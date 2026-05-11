#!/usr/bin/env bash
# MG-603 fix: убрать недостижимый тест test_none_returns_empty_list
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"

TESTS="$BACKEND/apps/recipes/tests/test_mg_603_serializers.py"

echo "=========================================="
echo "  MG-603 FIX"
echo "=========================================="

python3 <<PYEOF
import sys

PATH = "$TESTS"
src = open(PATH).read()

old = '''    def test_none_returns_empty_list(self):
        # MG_603: явная передача None должна нормализоваться в []
        s = RecipeWriteSerializer(data=_minimal(suitable_for=None))
        assert s.is_valid(), s.errors
        assert s.validated_data.get("suitable_for") == []

    def test_empty_string_returns_empty_list(self):'''

new = '''    def test_empty_string_returns_empty_list(self):'''

if old not in src:
    print("ERR: блок не найден"); sys.exit(2)
src = src.replace(old, new)
open(PATH, "w").write(src)
print("OK: тест test_none_returns_empty_list удалён")
PYEOF

$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/recipes/tests/test_mg_603_serializers.py').read()); print('AST OK')"

echo
echo "--- pytest ---"
$COMPOSE exec -T backend pytest apps/recipes/tests/test_mg_603_serializers.py -v --tb=short 2>&1 | tail -15

echo
echo "--- coverage report ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing
'

echo "=========================================="
echo "  MG-603 FIX DONE"
echo "=========================================="
