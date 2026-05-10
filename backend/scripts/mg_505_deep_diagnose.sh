#!/usr/bin/env bash
# MG-505 deep diagnose: реальная структура для интеграции cheat-meal
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"

echo "=== 1. MenuItem model (полностью) ==="
echo "--- apps/menu/models.py ---"
cat "$BACKEND/apps/menu/models.py"
echo

echo "=== 2. MenuItemSerializer ==="
echo "--- apps/menu/serializers.py (только MenuItem*) ---"
sed -n '1,80p' "$BACKEND/apps/menu/serializers.py"
echo

echo "=== 3. Generator: класс MenuGenerator + основной цикл генерации ==="
echo "--- apps/menu/generator.py (строки 150-280) ---"
sed -n '150,280p' "$BACKEND/apps/menu/generator.py" | cat -n
echo

echo "=== 4. Generator: _pick_for_role (425+) ==="
sed -n '420,540p' "$BACKEND/apps/menu/generator.py" | cat -n
echo

echo "=== 5. _WeeklyTracker (93+) ==="
sed -n '90,160p' "$BACKEND/apps/menu/generator.py" | cat -n
echo

echo "=== 6. apps/menu/views.py — где создаётся Menu и bulk_create MenuItem ==="
grep -nE "MenuItem|bulk_create|generator\.generate|class \w+View|def post|def create" \
  "$BACKEND/apps/menu/views.py" | head -40
echo

echo "--- Контекст вокруг bulk_create в views.py ---"
grep -B2 -A30 "bulk_create" "$BACKEND/apps/menu/views.py" | head -80
echo

echo "=== 7. Текущие маркеры MG в menu ==="
grep -rn "MG_50[0-9]\|MG_30[0-9]\|MG_40[0-9]" "$BACKEND/apps/menu/" | head -20
echo

echo "=== DONE ==="
