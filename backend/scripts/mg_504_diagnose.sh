#!/usr/bin/env bash
# MG-504 diagnose: bedtime_hour, cheat_meal_interval, last_cheat_meal_date в Profile
set -euo pipefail

ROOT="${ROOT:-/opt/menugen}"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
MOBILE="$ROOT/mobile/menugen_app"

echo "=== MG-504 DIAGNOSE ==="
echo

echo "--- Profile model: backend/apps/users/models.py ---"
if [[ -f "$BACKEND/apps/users/models.py" ]]; then
  grep -nE "bedtime_hour|cheat_meal_interval|last_cheat_meal_date|class Profile" "$BACKEND/apps/users/models.py" || echo "  (не найдено: поля MG-504)"
else
  echo "FAIL: нет $BACKEND/apps/users/models.py"
fi
echo

echo "--- Сериализаторы users: backend/apps/users/serializers.py ---"
if [[ -f "$BACKEND/apps/users/serializers.py" ]]; then
  grep -nE "bedtime_hour|cheat_meal_interval|last_cheat_meal_date|MG_501|class Profile" "$BACKEND/apps/users/serializers.py" || echo "  (не найдено: поля MG-504)"
else
  echo "FAIL: нет $BACKEND/apps/users/serializers.py"
fi
echo

echo "--- Сериализаторы family: backend/apps/family/serializers.py ---"
if [[ -f "$BACKEND/apps/family/serializers.py" ]]; then
  grep -nE "bedtime_hour|cheat_meal_interval|last_cheat_meal_date|MG_501|MG_504|class Profile" "$BACKEND/apps/family/serializers.py" || echo "  (не найдено: поля MG-504)"
else
  echo "FAIL: нет $BACKEND/apps/family/serializers.py"
fi
echo

echo "--- Миграции users ---"
ls -1 "$BACKEND/apps/users/migrations/"*.py 2>/dev/null | tail -10 || echo "  (миграций нет)"
echo

echo "--- Frontend types ---"
if [[ -f "$WEB/src/types/index.ts" ]]; then
  grep -nE "bedtime_hour|cheatMealInterval|cheat_meal_interval|last_cheat_meal_date|UserProfile|MG_504" "$WEB/src/types/index.ts" || echo "  (не найдено: типы MG-504)"
fi
echo

echo "--- Mobile (Flutter) Profile model ---"
if [[ -d "$MOBILE/lib" ]]; then
  grep -rnE "bedtime_hour|cheat_meal_interval|last_cheat_meal_date" "$MOBILE/lib" 2>/dev/null || echo "  (не найдено)"
fi
echo

echo "=== DONE MG-504 DIAGNOSE ==="
