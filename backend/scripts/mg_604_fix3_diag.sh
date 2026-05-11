#!/usr/bin/env bash
# MG-604 fix-3: посмотреть текущий тест и привести к рабочему виду
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"

TEST="$BACKEND/apps/menu/tests/test_mg_604_portions.py"

echo "=========================================="
echo "  MG-604 FIX-3 portions.py"
echo "=========================================="

echo
echo "--- [1] Текущее состояние test_nutrition_exception_falls_through_to_povar ---"
grep -n "BoomDict" "$TEST" || echo "BoomDict не найден"
echo
sed -n '/def test_nutrition_exception_falls_through_to_povar/,/def test_povar_raw_with_servings_normalized/p' "$TEST"

echo
echo "--- [2] Запуск pytest этого конкретного теста с verbose ---"
$COMPOSE exec -T backend pytest apps/menu/tests/test_mg_604_portions.py::TestRecipePortionGrams::test_nutrition_exception_falls_through_to_povar -v --tb=long 2>&1 | tail -20

echo
echo "--- [3] Coverage именно этого теста ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/tests/test_mg_604_portions.py -q --tb=no 2>&1 | tail -3
  echo
  coverage report --rcfile=.coveragerc --show-missing | grep portions
'

echo "=========================================="
