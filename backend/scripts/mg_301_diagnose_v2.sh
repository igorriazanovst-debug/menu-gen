#!/usr/bin/env bash
# MG-301 diagnose v2: посмотреть содержимое моделей, генератора, миграции и тестов.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
MENU_APP="${PROJECT_ROOT}/backend/apps/menu"
RECIPES_APP="${PROJECT_ROOT}/backend/apps/recipes"

echo "=== MG-301 DIAGNOSE v2 === $(date -Is)"
echo

echo "===== [A] apps/menu/models.py (целиком) ====="
cat -n "${MENU_APP}/models.py"
echo
echo "===== [B] apps/menu/generator.py (целиком) ====="
cat -n "${MENU_APP}/generator.py"
echo
echo "===== [C] apps/menu/migrations/0006_component_role.py ====="
cat -n "${MENU_APP}/migrations/0006_component_role.py"
echo
echo "===== [D] apps/menu/tests/test_menu.py ====="
cat -n "${MENU_APP}/tests/test_menu.py"
echo
echo "===== [E] apps/recipes/models.py — поля Recipe (выжимка) ====="
awk '
  /^class Recipe\b/ { in_recipe=1 }
  in_recipe && /^class [A-Z]/ && !/^class Recipe\b/ { in_recipe=0 }
  in_recipe { print NR": "$0 }
' "${RECIPES_APP}/models.py" | sed -n '1,200p'
echo
echo "===== [F] FoodGroup / suitable_for choices (где определены) ====="
grep -nE "FoodGroup|food_group|suitable_for|protein_type|grain_type" "${RECIPES_APP}/models.py" | head -50
echo
echo "===== [G] apps/menu/serializers.py (только классы и поля) ====="
grep -nE "^\s*(class |Meta|fields\s*=)" "${MENU_APP}/serializers.py" | head -50
echo
echo "===== [H] apps/menu/views.py (только endpoints) ====="
grep -nE "^\s*(class |def |path\(|url\()" "${MENU_APP}/views.py" | head -40
echo
echo "===== [I] apps/menu/urls.py ====="
cat -n "${MENU_APP}/urls.py"
echo
echo "=== DIAGNOSE v2 DONE ==="
