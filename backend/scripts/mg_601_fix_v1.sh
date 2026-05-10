#!/usr/bin/env bash
# MG-601 fix tests v1: добавить fruit/dairy в фикстуры падающих тестов
set -eu
ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
F="${BACKEND}/apps/menu/tests/test_mg_601_integration.py"

cp -p "$F" "/tmp/mg_601_fix_${TS}_test_mg_601_integration.py.bak"
echo "[0] backup: /tmp/mg_601_fix_${TS}_test_mg_601_integration.py.bak"

$COMPOSE exec -T backend python <<'PYEOF'
from pathlib import Path
p = Path("apps/menu/tests/test_mg_601_integration.py")
src = p.read_text(encoding="utf-8")

# Доп. строки в каждом for-блоке: fruit + dairy + grain где их не хватало.

replacements = [
    # TestMG303CalorieDistribution.test_calorie_distribution_3meal
    (
        '        for i in range(15):\n'
        '            _mk_recipe(f"P{i}", "protein", kcal=Decimal(str(200 + i * 30)))\n'
        '            _mk_recipe(f"G{i}", "grain", kcal=Decimal(str(150 + i * 30)))\n'
        '            _mk_recipe(f"V{i}", "vegetable", kcal=Decimal(str(50 + i * 20)))\n',
        '        for i in range(15):\n'
        '            _mk_recipe(f"P{i}", "protein", kcal=Decimal(str(200 + i * 30)))\n'
        '            _mk_recipe(f"G{i}", "grain", kcal=Decimal(str(150 + i * 30)))\n'
        '            _mk_recipe(f"V{i}", "vegetable", kcal=Decimal(str(50 + i * 20)))\n'
        '            _mk_recipe(f"F{i}", "fruit", kcal=Decimal(str(60 + i * 10)))\n'
        '            _mk_recipe(f"D{i}", "dairy", kcal=Decimal(str(120 + i * 10)))\n',
    ),
    # TestMG502OilLimit.test_oil_heavy_recipes_not_dominating
    (
        '        for i in range(5):\n'
        '            _mk_recipe(f"Oily-P{i}", "protein", oil_tsp=Decimal("10.0"))\n'
        '            _mk_recipe(f"Light-P{i}", "protein", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"Oily-G{i}", "grain", oil_tsp=Decimal("10.0"))\n'
        '            _mk_recipe(f"Light-G{i}", "grain", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"V{i}", "vegetable", oil_tsp=Decimal("0.0"))\n',
        '        for i in range(5):\n'
        '            _mk_recipe(f"Oily-P{i}", "protein", oil_tsp=Decimal("10.0"))\n'
        '            _mk_recipe(f"Light-P{i}", "protein", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"Oily-G{i}", "grain", oil_tsp=Decimal("10.0"))\n'
        '            _mk_recipe(f"Light-G{i}", "grain", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"V{i}", "vegetable", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"F{i}", "fruit", oil_tsp=Decimal("0.0"))\n'
        '            _mk_recipe(f"D{i}", "dairy", oil_tsp=Decimal("0.0"))\n',
    ),
    # TestMG503AddedSugar.test_no_added_sugar_in_main_meals
    (
        '        for i in range(5):\n'
        '            _mk_recipe(f"SweetP{i}", "protein", has_added_sugar=True)\n'
        '            _mk_recipe(f"NormalP{i}", "protein", has_added_sugar=False)\n'
        '            _mk_recipe(f"SweetG{i}", "grain", has_added_sugar=True)\n'
        '            _mk_recipe(f"NormalG{i}", "grain", has_added_sugar=False)\n'
        '            _mk_recipe(f"V{i}", "vegetable", has_added_sugar=False)\n',
        '        for i in range(5):\n'
        '            _mk_recipe(f"SweetP{i}", "protein", has_added_sugar=True)\n'
        '            _mk_recipe(f"NormalP{i}", "protein", has_added_sugar=False)\n'
        '            _mk_recipe(f"SweetG{i}", "grain", has_added_sugar=True)\n'
        '            _mk_recipe(f"NormalG{i}", "grain", has_added_sugar=False)\n'
        '            _mk_recipe(f"V{i}", "vegetable", has_added_sugar=False)\n'
        '            _mk_recipe(f"F{i}", "fruit", has_added_sugar=False)\n'
        '            _mk_recipe(f"D{i}", "dairy", has_added_sugar=False)\n',
    ),
    # TestMG302RedMeatWeekly.test_red_meat_capped_under_500g_per_week
    (
        '        for i in range(5):\n'
        '            _mk_recipe(f"Beef{i}", "protein",\n'
        '                       protein_type="animal", is_red_meat=True,\n'
        '                       servings_normalized=1)\n'
        '            _mk_recipe(f"Beans{i}", "protein", protein_type="plant")\n'
        '            _mk_recipe(f"Fish{i}", "protein",\n'
        '                       protein_type="animal", is_fatty_fish=True)\n'
        '            _mk_recipe(f"G{i}", "grain")\n'
        '            _mk_recipe(f"V{i}", "vegetable")\n',
        '        for i in range(5):\n'
        '            _mk_recipe(f"Beef{i}", "protein",\n'
        '                       protein_type="animal", is_red_meat=True,\n'
        '                       servings_normalized=1)\n'
        '            _mk_recipe(f"Beans{i}", "protein", protein_type="plant")\n'
        '            _mk_recipe(f"Fish{i}", "protein",\n'
        '                       protein_type="animal", is_fatty_fish=True)\n'
        '            _mk_recipe(f"G{i}", "grain")\n'
        '            _mk_recipe(f"V{i}", "vegetable")\n'
        '            _mk_recipe(f"F{i}", "fruit")\n'
        '            _mk_recipe(f"D{i}", "dairy")\n',
    ),
    # TestMG601MainMealComposition.test_main_meal_three_components_with_target
    (
        '        for i in range(5):\n'
        '            _mk_recipe(f"P{i}", "protein", kcal=Decimal("250"))\n'
        '            _mk_recipe(f"G{i}", "grain", kcal=Decimal("200"))\n'
        '            _mk_recipe(f"V{i}", "vegetable", kcal=Decimal("80"))\n',
        '        for i in range(5):\n'
        '            _mk_recipe(f"P{i}", "protein", kcal=Decimal("250"))\n'
        '            _mk_recipe(f"G{i}", "grain", kcal=Decimal("200"))\n'
        '            _mk_recipe(f"V{i}", "vegetable", kcal=Decimal("80"))\n'
        '            _mk_recipe(f"F{i}", "fruit", kcal=Decimal("70"))\n'
        '            _mk_recipe(f"D{i}", "dairy", kcal=Decimal("120"))\n',
    ),
]

for old, new in replacements:
    if old not in src:
        print(f"  WARN: фрагмент не найден (первые 80 символов): {old[:80]!r}")
        continue
    src = src.replace(old, new, 1)
    print(f"  patched: {new.splitlines()[0][:60]}...")

p.write_text(src, encoding="utf-8")
print("OK saved")
PYEOF

echo
echo "[1] AST validate..."
$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/tests/test_mg_601_integration.py').read()); print('OK')"

echo
echo "[2] прогон новых тестов..."
$COMPOSE exec -T backend pytest apps/menu/tests/test_mg_601_integration.py -v --tb=short 2>&1 | tail -80
