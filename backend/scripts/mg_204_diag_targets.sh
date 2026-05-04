#!/usr/bin/env bash
MP="/opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx"
echo "### grep targets / userProfile / MenuGrid / NutritionTargets ###"
grep -nE "targets|userProfile|MenuGrid|NutritionTargets|MG_204_V_menu" "$MP"
echo
echo "### Контекст 490-545 ###"
sed -n '490,545p' "$MP" | cat -n
