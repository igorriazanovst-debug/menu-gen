#!/usr/bin/env bash
# MG-505 diagnose: is_cheat_meal в MenuItem + слот cheat-meal в генераторе
set -euo pipefail

ROOT="${ROOT:-/opt/menugen}"
BACKEND="$ROOT/backend"

echo "=== MG-505 DIAGNOSE ==="
echo

echo "--- MenuItem model: backend/apps/menu/models.py ---"
if [[ -f "$BACKEND/apps/menu/models.py" ]]; then
  grep -nE "is_cheat_meal|class MenuItem|class Menu\b" "$BACKEND/apps/menu/models.py" || echo "  (поле is_cheat_meal не найдено)"
else
  echo "FAIL: нет $BACKEND/apps/menu/models.py"
fi
echo

echo "--- MenuItemSerializer: backend/apps/menu/serializers.py ---"
if [[ -f "$BACKEND/apps/menu/serializers.py" ]]; then
  grep -nE "is_cheat_meal|class MenuItemSerializer" "$BACKEND/apps/menu/serializers.py" || echo "  (поле is_cheat_meal не найдено)"
fi
echo

echo "--- Generator: backend/apps/menu/generator.py ---"
if [[ -f "$BACKEND/apps/menu/generator.py" ]]; then
  grep -nE "is_cheat_meal|cheat_meal|last_cheat_meal_date|MG_502_503|MG_505|class MenuGenerator|_pick_for_role|class _WeeklyTracker|tracker\.add" "$BACKEND/apps/menu/generator.py" | head -50 || echo "  (cheat-meal логика не найдена)"
else
  echo "FAIL: нет $BACKEND/apps/menu/generator.py"
fi
echo

echo "--- Миграции menu ---"
ls -1 "$BACKEND/apps/menu/migrations/"*.py 2>/dev/null | tail -10 || echo "  (миграций нет)"
echo

echo "=== DONE MG-505 DIAGNOSE ==="
