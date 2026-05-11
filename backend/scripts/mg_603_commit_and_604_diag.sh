#!/usr/bin/env bash
# MG-603 commit + MG-604 diagnose
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg604_diag_${TS}.txt"

cd "$ROOT"

echo "=========================================="
echo "  MG-603 COMMIT"
echo "=========================================="

git add backend/apps/recipes/tests/test_mg_603_serializers.py
git status --short
git commit -m "MG-603: recipes/serializers.py coverage 77% → 100%

Tests: apps/recipes/tests/test_mg_603_serializers.py — 21 unit-теста

- validate_ingredients: не-list, item без 'name', item не dict, valid
- validate_steps: не-list, item без 'text', item не dict
- validate_suitable_for: пустая строка, не-list, недопустимое значение,
  все allowed values, пустой список
- validate (food_group): grain без grain_type → 400, grain c grain_type → ok,
  protein без protein_type → 400, protein c protein_type → ok,
  vegetable/no-food-group без constraints,
  partial_update: grain_type подтягивается из instance,
  смена food_group без required-поля → 400

Coverage:
- apps/recipes/serializers.py: 77% → 100%
- TOTAL: 94% → 95%
- Тестов: 167 → 188"

git log -1 --oneline

echo
echo "=========================================="
echo "  MG-604 DIAGNOSE  ($TS)"
echo "  Остатки coverage: recipes/permissions.py + recipes/views.py"
echo "                    menu/exceptions.py + menu/portions.py"
echo "=========================================="

exec > >(tee "$OUT") 2>&1

echo
echo "--- [1] apps/recipes/permissions.py (полный) ---"
$COMPOSE exec -T backend cat -n apps/recipes/permissions.py

echo
echo "--- [2] apps/recipes/views.py: строки 24-33 (RecipeCountryListView) и 141-145 (RecipeAuthorApplyView.perform_create) ---"
$COMPOSE exec -T backend bash -lc 'sed -n "19,35p;139,146p" apps/recipes/views.py | nl -ba'

echo
echo "--- [3] apps/menu/exceptions.py (строки 42, 77) ---"
$COMPOSE exec -T backend cat -n apps/menu/exceptions.py

echo
echo "--- [4] apps/menu/portions.py (строки 33, 54-55, 81-82, 93-94) ---"
$COMPOSE exec -T backend cat -n apps/menu/portions.py

echo
echo "--- [5] Сущ. тесты для permissions / views / exceptions / portions ---"
$COMPOSE exec -T backend bash -lc '
  echo "--- apps/recipes/tests/test_recipes.py (permissions/views тесты) ---"
  grep -nE "def test_|RecipeAuthor|countries|IsRecipeAuthor|IsAuthorOrAdmin" apps/recipes/tests/test_recipes.py | head -40
  echo
  echo "--- apps/menu/tests/ — тесты для exceptions/portions ---"
  grep -rnE "MenuGeneratorError|portions|portion_grams" apps/menu/tests/ | head -20
'

echo
echo "--- [6] apps/menu/exceptions.py: что бросает строки 42, 77 ---"
$COMPOSE exec -T backend bash -lc 'sed -n "35,50p" apps/menu/exceptions.py; echo "---"; sed -n "70,85p" apps/menu/exceptions.py'

echo
echo "--- [7] apps/menu/portions.py — функции вокруг missing lines ---"
$COMPOSE exec -T backend bash -lc 'grep -nE "^def |^class " apps/menu/portions.py'

echo
echo "=========================================="
echo "  MG-604 DIAG DONE → $OUT"
echo "=========================================="
