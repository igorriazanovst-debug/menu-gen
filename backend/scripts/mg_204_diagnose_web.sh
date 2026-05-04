#!/usr/bin/env bash
# MG-204 diagnose: текущее состояние web-фронта (React) после MG-201/203/205.
# Что уже есть в types/index.ts, ProfilePage, FamilyMember*, MenuPage по части КБЖУ и meal_plan_type.

set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"

echo "=========================================="
echo "MG-204 DIAGNOSE: web frontend"
echo "=========================================="
echo

echo "### 1. Структура src/ (top-level) ###"
ls -la "$SRC" 2>/dev/null || { echo "NO $SRC"; exit 1; }
echo

echo "### 2. types/index.ts: UserProfile / Profile / FamilyMember / MealPlanType ###"
if [ -f "$SRC/types/index.ts" ]; then
  echo "--- grep для KEYS КБЖУ и meal_plan ---"
  grep -nE "calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|targets_calculated|MealPlanType" "$SRC/types/index.ts" || echo "  (ничего не найдено)"
  echo
  echo "--- весь UserProfile / Profile / FamilyMember interface (контекст) ---"
  awk '/^export (interface|type) (UserProfile|Profile|FamilyMember|MealPlanType)/,/^}|^;$/' "$SRC/types/index.ts" || true
else
  echo "  NO $SRC/types/index.ts"
fi
echo

echo "### 3. Поиск страниц и компонентов Profile / Family / Menu ###"
echo "--- Pages ---"
find "$SRC" -type d \( -iname "Profile*" -o -iname "Family*" -o -iname "Menu*" \) 2>/dev/null
echo
echo "--- Файлы ProfilePage, FamilyMember*, MenuPage ---"
find "$SRC" -type f \( -iname "ProfilePage.*" -o -iname "FamilyMember*" -o -iname "MenuPage.*" -o -iname "DayNutritionSummary.*" \) 2>/dev/null
echo

echo "### 4. ProfilePage.tsx — что уже есть про КБЖУ и meal_plan ###"
PROFILE_PAGE=$(find "$SRC" -type f -iname "ProfilePage.tsx" | head -1)
if [ -n "$PROFILE_PAGE" ]; then
  echo "Файл: $PROFILE_PAGE"
  echo "--- grep по ключам ---"
  grep -nE "calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|targets_calculated" "$PROFILE_PAGE" || echo "  (ничего не найдено в ProfilePage.tsx)"
  echo
  echo "--- размер ---"
  wc -l "$PROFILE_PAGE"
else
  echo "  NO ProfilePage.tsx"
fi
echo

echo "### 5. FamilyMember edit / form — что уже есть ###"
for f in $(find "$SRC" -type f \( -iname "FamilyMember*Form*" -o -iname "FamilyMember*Edit*" -o -iname "FamilyMember*Modal*" -o -iname "FamilyPage*" \) 2>/dev/null); do
  echo "--- $f ---"
  grep -nE "calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type" "$f" || echo "  (ничего не найдено)"
  echo
done
echo

echo "### 6. MenuPage.tsx — что уже есть про дневные цели КБЖУ ###"
MENU_PAGE=$(find "$SRC" -type f -iname "MenuPage.tsx" | head -1)
if [ -n "$MENU_PAGE" ]; then
  echo "Файл: $MENU_PAGE"
  grep -nE "calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|DayNutritionSummary|nutrition_summary" "$MENU_PAGE" || echo "  (ничего не найдено)"
  echo
  wc -l "$MENU_PAGE"
else
  echo "  NO MenuPage.tsx"
fi
echo

echo "### 7. api/users.ts, api/family.ts — поля в request/response типах ###"
for f in $(find "$SRC/api" -type f -name "*.ts" 2>/dev/null); do
  if grep -qE "users/me|family/members|getProfile|updateProfile" "$f"; then
    echo "--- $f ---"
    grep -nE "calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|users/me|family/members" "$f" || true
    echo
  fi
done
echo

echo "### 8. Реальный ответ /api/v1/users/me (как backend сейчас отдаёт) ###"
echo "--- Профиль pid=1 через Django shell ---"
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py shell -c "
from apps.users.models import Profile, User
from apps.users.serializers import UserMeSerializer
p = Profile.objects.first()
if p:
    u = p.user
    s = UserMeSerializer(u)
    import json
    print(json.dumps(s.data, ensure_ascii=False, indent=2, default=str))
else:
    print('NO PROFILE')
" 2>&1 | head -80
echo

echo "### 9. tsc --noEmit baseline (есть ли ошибки уже сейчас) ###"
cd "$WEB"
if command -v npx >/dev/null 2>&1; then
  echo "Запускаю npx tsc --noEmit ..."
  npx tsc --noEmit 2>&1 | head -50 || true
  echo "(возможно усечено)"
else
  echo "  npx не найден"
fi
echo

echo "### 10. Версия Node, наличие react-router, формочных либ ###"
node -v 2>/dev/null || echo "  no node"
if [ -f "$WEB/package.json" ]; then
  echo "--- зависимости (часть) ---"
  python3 -c "
import json
p=json.load(open('$WEB/package.json'))
deps={**p.get('dependencies',{}), **p.get('devDependencies',{})}
keys=['react','react-dom','react-router','react-router-dom','@tanstack/react-query','axios','zod','react-hook-form','formik','tailwindcss','typescript']
for k in keys:
    for dk in deps:
        if k in dk: print(f'  {dk}: {deps[dk]}')
"
fi
echo

echo "=========================================="
echo "DIAGNOSE END"
echo "=========================================="
