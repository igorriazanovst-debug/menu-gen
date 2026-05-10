#!/usr/bin/env bash
# MG-504 post-apply diagnose: что уже сделано, что осталось
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== POST-APPLY DIAGNOSE MG-504 ==="
echo

echo "--- 1) DB credentials из .env ---"
grep -E "^(DB_USER|DB_NAME|DB_PASSWORD)=" "$ROOT/.env" | sed 's/=.*/=***/'
echo

echo "--- 2) MG_504 маркеры в backend ---"
grep -rn "MG_504_V" "$BACKEND/apps" 2>/dev/null || echo "  (нет маркеров)"
echo

echo "--- 3) Profile model: новые поля ---"
grep -nE "bedtime_hour|cheat_meal_interval|last_cheat_meal_date" "$BACKEND/apps/users/models.py" || echo "  (поля не добавлены)"
echo

echo "--- 4) users/serializers.py: MG504_FIELDS ---"
grep -nE "MG504_FIELDS|MG_504" "$BACKEND/apps/users/serializers.py" || echo "  (не пропатчен)"
echo

echo "--- 5) family/serializers.py: MG_504 ---"
grep -nE "MG504_FIELDS|MG_504|bedtime_hour" "$BACKEND/apps/family/serializers.py" || echo "  (не пропатчен)"
echo

echo "--- 6) Миграции users ---"
ls -1 "$BACKEND/apps/users/migrations/"*.py 2>/dev/null | tail -10
echo

echo "--- 7) Frontend types ---"
grep -nE "bedtime_hour|cheat_meal_interval|MG_504_V_types" "$WEB/src/types/index.ts" 2>/dev/null || echo "  (не пропатчен)"
echo

echo "--- 8) Состояние контейнеров ---"
$COMPOSE ps 2>/dev/null | grep -v WARN
echo

echo "--- 9) Проверка коннекта к БД через .env ---"
DB_USER_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_USER"' 2>/dev/null)
DB_NAME_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_DB"' 2>/dev/null)
echo "  POSTGRES_USER=$DB_USER_REAL"
echo "  POSTGRES_DB=$DB_NAME_REAL"
echo

echo "=== DONE ==="
