#!/usr/bin/env bash
# 605.A diag: точка внедрения mode в генератор
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== A1. MenuGenerator __init__ (полностью) ==="
$COMPOSE exec -T backend sed -n '155,200p' apps/menu/generator.py
echo

echo "=== A2. MenuGenerator.generate — основной цикл (160-275) ==="
$COMPOSE exec -T backend sed -n '186,275p' apps/menu/generator.py
echo

echo "=== A3. _collect_allergens / _get_hard_exclude (полностью) ==="
$COMPOSE exec -T backend grep -nA20 "def _get_hard_exclude\|def _get_calorie_target\|def _collect_allergens" apps/menu/generator.py
echo

echo "=== A4. _ensure_veg_fruit_servings (полностью) ==="
$COMPOSE exec -T backend sed -n '332,420p' apps/menu/generator.py
echo

echo "=== A5. tests test_menu.py — как сейчас тестируется multi-member (если есть) ==="
$COMPOSE exec -T backend grep -nB2 -A8 "members\|FamilyMember.objects.create" apps/menu/tests/test_menu.py | head -60
echo

echo "=== A6. test_mg_303.py — есть ли мульти-член тесты ==="
$COMPOSE exec -T backend grep -nB1 -A5 "FamilyMember.objects.create\|members=" apps/menu/tests/test_mg_303.py | head -40
echo

echo "=== A7. _meal_target_cal / _meal_cal_target ==="
$COMPOSE exec -T backend grep -nA8 "def _meal_target_cal\|_meal_cal_target\[" apps/menu/generator.py | head -40
echo

echo "=== A8. Полный generate() (с 162 строки и далее, чтобы видеть структуру) ==="
$COMPOSE exec -T backend wc -l apps/menu/generator.py
echo

echo "=== A9. test_menu.py — генерация: где POST на /menu/generate ==="
$COMPOSE exec -T backend grep -nB2 -A10 "menu-generate\|/generate/" apps/menu/tests/test_menu.py | head -50
echo

echo "=== A10. apps/menu/tests/conftest.py (если есть) ==="
$COMPOSE exec -T backend bash -c 'cat apps/menu/tests/conftest.py 2>/dev/null || echo "нет conftest.py в apps/menu/tests"'
echo
$COMPOSE exec -T backend bash -c 'cat /app/conftest.py 2>/dev/null || cat conftest.py 2>/dev/null'
echo

echo "=== DONE 605.A diag ==="
