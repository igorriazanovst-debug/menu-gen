#!/usr/bin/env bash
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"

echo "### A. Файлы реально на диске? ###"
for f in \
  "$SRC/components/family/FamilyMemberEditModal.tsx" \
  "$SRC/components/menu/DayNutritionSummary.tsx" \
  "$SRC/pages/Family/FamilyPage.tsx" \
  "$SRC/pages/Menu/MenuPage.tsx" \
  "$SRC/types/index.ts" \
  "$SRC/api/family.ts"; do
  if [ -f "$f" ]; then
    echo "  $f  $(stat -c '%y  %s байт' "$f")"
  else
    echo "  $f  ❌ НЕТ"
  fi
done
echo

echo "### B. Маркеры в файлах ###"
grep -l "MG_204_V_family" "$SRC/pages/Family/FamilyPage.tsx" "$SRC/components/family/FamilyMemberEditModal.tsx" 2>/dev/null || echo "  family маркер не найден!"
grep -l "MG_204_V_summary" "$SRC/components/menu/DayNutritionSummary.tsx" 2>/dev/null || echo "  summary маркер не найден!"
grep -l "MG_204_V_types"   "$SRC/types/index.ts" 2>/dev/null || echo "  types маркер не найден!"
grep -l "MG_204_V_api"     "$SRC/api/family.ts" 2>/dev/null || echo "  api маркер не найден!"
grep -l "MG_204_V_menu"    "$SRC/pages/Menu/MenuPage.tsx" 2>/dev/null || echo "  menu маркер не найден!"
echo

echo "### C. FamilyPage: где импортируется FamilyMemberEditModal и кнопка ✎ ###"
grep -nE "FamilyMemberEditModal|setEditing|✎|m\.profile\?\.calorie_target" "$SRC/pages/Family/FamilyPage.tsx" | head -20
echo

echo "### D. MenuPage: импорт + использование DayNutritionSummary ###"
grep -nE "DayNutritionSummary|targets:" "$SRC/pages/Menu/MenuPage.tsx" | head -20
echo

echo "### E. Какие процессы CRA / dev-server / nginx крутятся ###"
ps -ef | grep -E "react-scripts|webpack|vite|node.*menugen-web|nginx" | grep -v grep | head -20
echo

echo "### F. Есть ли build/ или dist/ (production-сборка)? ###"
ls -lad "$WEB/build" "$WEB/dist" 2>/dev/null
echo

echo "### G. Что отдаётся на 31.192.110.121:8081 — это dev или статика? ###"
ss -ltnp 2>/dev/null | grep ":8081" | head -5
echo
echo "--- nginx config с 8081 ---"
grep -rnE "8081|menugen-web" /etc/nginx/ 2>/dev/null | head -20
echo

echo "### H. Свежий index.html (SHA того, что отдаётся) ###"
curl -s "http://31.192.110.121:8081/" -o /tmp/served_index.html 2>/dev/null
if [ -f /tmp/served_index.html ]; then
  echo "  size: $(stat -c %s /tmp/served_index.html)"
  echo "  sha256:"
  sha256sum /tmp/served_index.html
  echo "  основные js bundle ссылки:"
  grep -oE 'src="[^"]*\.js[^"]*"' /tmp/served_index.html | head -5
fi
echo

echo "### I. Что внутри FamilyPage ровно сейчас (первые 40 строк) ###"
sed -n '1,40p' "$SRC/pages/Family/FamilyPage.tsx"
