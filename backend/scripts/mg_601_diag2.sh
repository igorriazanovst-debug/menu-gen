#!/usr/bin/env bash
# MG-601 deep diagnose: модели, фикстуры, missing lines, recipes coverage
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== 1. Recipe model — поля для фикстур ==="
$COMPOSE exec -T backend cat apps/recipes/models.py
echo

echo "=== 2. Menu/MenuItem model ==="
$COMPOSE exec -T backend cat apps/menu/models.py
echo

echo "=== 3. Profile / FamilyMember модели ==="
$COMPOSE exec -T backend cat apps/users/models.py
echo
echo "--- apps/family/models.py ---"
$COMPOSE exec -T backend cat apps/family/models.py
echo

echo "=== 4. Существующие фикстуры в test_menu.py (как создают setup) ==="
$COMPOSE exec -T backend sed -n '1,55p' apps/menu/tests/test_menu.py
echo

echo "=== 5. Существующие фикстуры в test_mg_301.py (setup_full) ==="
$COMPOSE exec -T backend sed -n '1,60p' apps/menu/tests/test_mg_301.py
echo

echo "=== 6. /app/conftest.py ==="
$COMPOSE exec -T backend cat /app/conftest.py
echo

echo "=== 7. coverage report --show-missing apps/menu/ + apps/recipes/ ==="
$COMPOSE exec -T backend bash -c '
  coverage run -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -3
  echo
  coverage report --include="apps/menu/*,apps/recipes/*" --show-missing 2>&1
'
echo

echo "=== 8. Какие endpoints есть в apps/menu/urls.py ==="
$COMPOSE exec -T backend cat apps/menu/urls.py
echo

echo "=== 9. apps/menu/views.py — список view-классов ==="
$COMPOSE exec -T backend grep -nE "^class |def (get|post|patch|delete|put)" apps/menu/views.py
echo

echo "=== 10. apps/recipes/views.py + urls.py ==="
$COMPOSE exec -T backend cat apps/recipes/urls.py
echo "--- views.py: классы ---"
$COMPOSE exec -T backend grep -nE "^class |def (get|post|patch|delete|put)" apps/recipes/views.py
echo

echo "=== 11. test_recipes.py — текущие тесты для apps/recipes ==="
$COMPOSE exec -T backend grep -nE "def test_|class " apps/recipes/tests/test_recipes.py
echo
$COMPOSE exec -T backend grep -nE "def test_|class " apps/recipes/tests/test_mg_501.py
echo

echo "=== 12. Recipe cheat-friendly: примеры существующих рецептов в фикстурах test_menu ==="
$COMPOSE exec -T backend grep -nA5 "Recipe.objects.create\|setup_full\|fixture" apps/menu/tests/test_menu.py | head -50
echo

echo "=== 13. Что генерится в setup для test_menu — копия первых 50 строк ==="
$COMPOSE exec -T backend sed -n '1,50p' apps/menu/tests/test_menu.py
echo

echo "=== 14. apps/menu/serializers.py — список сериализаторов ==="
$COMPOSE exec -T backend grep -nE "^class " apps/menu/serializers.py
echo

echo "=== 15. apps/menu/exceptions.py ==="
$COMPOSE exec -T backend cat apps/menu/exceptions.py
echo

echo "=== 16. Recipe constants: food_group/protein_type/grain_type values ==="
$COMPOSE exec -T backend grep -nE "FOOD_GROUP|PROTEIN_TYPE|GRAIN_TYPE|food_group|protein_type|grain_type|added_sugar|oil_tsp" apps/recipes/models.py | head -40
echo

echo "=== DONE MG-601 DEEP DIAG ==="
