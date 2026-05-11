#!/usr/bin/env bash
set -eu
COMPOSE="docker compose -f /opt/menugen/docker-compose.yml"

echo "=== 1. _build_pools_by_role и role mapping (что считается protein) ==="
$COMPOSE exec -T backend grep -nA40 "def _build_pools_by_role\|ROLE_FOOD_GROUPS\|FOOD_GROUP_ROLE" apps/menu/generator.py | head -80
echo

echo "=== 2. Какие food_group значения принимает Recipe ==="
$COMPOSE exec -T backend grep -nA5 "food_group\|FoodGroup" apps/recipes/models.py | head -40
echo

echo "=== 3. Как существующие тесты test_mg_303/304 создают рецепты ==="
$COMPOSE exec -T backend grep -nB1 -A3 "food_group" apps/menu/tests/test_mg_303.py | head -40
echo
$COMPOSE exec -T backend grep -nB1 -A3 "food_group" apps/menu/tests/test_mg_304.py | head -40
echo

echo "=== 4. setup_full из test_mg_301.py — пример рабочей фикстуры ==="
$COMPOSE exec -T backend sed -n '1,70p' apps/menu/tests/test_mg_301.py
echo

echo "=== 5. Все используемые food_group/protein_type в тестах ==="
$COMPOSE exec -T backend grep -rE "food_group=|protein_type=" apps/menu/tests/ apps/recipes/tests/ 2>/dev/null | head -30
echo

echo "=== 6. Полностью _build_pools_by_role до 100 строк после ==="
$COMPOSE exec -T backend awk '/def _build_pools_by_role/,/^    def /' apps/menu/generator.py | head -80
echo

echo "=== DONE ==="
