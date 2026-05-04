#!/usr/bin/env bash
set -euo pipefail
MP="/opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx"
echo "### Контекст 510-560 ###"
sed -n '510,560p' "$MP" | cat -n
echo
echo "### Все вхождения MealCard и DayNutritionSummary ###"
grep -n "MealCard\|DayNutritionSummary\|dayItems" "$MP"
