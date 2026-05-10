#!/usr/bin/env bash
# Контекст вокруг патча family/serializers.py + полная структура файла
set -eu

ROOT="/opt/menugen"
F="$ROOT/backend/apps/family/serializers.py"

echo "=== Контекст строк 70-90 family/serializers.py ==="
sed -n '70,90p' "$F" | cat -n
echo

echo "=== Все классы и поля Profile* ==="
grep -nE "^class |bedtime_hour|cheat_meal_interval|last_cheat_meal_date|fields\s*=|MG504_FIELDS|MG501_FIELDS" "$F"
echo

echo "=== Полный файл family/serializers.py ==="
cat "$F"
