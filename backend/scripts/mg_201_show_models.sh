#!/usr/bin/env bash
# Показать класс Profile целиком (или хотя бы enum MealPlan и поля рядом).
set -euo pipefail

F="/opt/menugen/backend/apps/users/models.py"

echo "=== $F ==="
echo
echo "--- enum MealPlan / Goal / ActivityLevel ---"
# Найдём строки с class XxxChoices/TextChoices внутри Profile
grep -nE 'class [A-Z][a-zA-Z]+\(.*Choices' "$F" || true

echo
echo "--- ВСЕ class/def в файле (с отступом и номером строки) ---"
grep -nE '^(class |    class |def |    def )' "$F" || true

echo
echo "--- ВСЕ упоминания 'Profile' в файле ---"
grep -nE 'Profile' "$F" || true

echo
echo "--- Строки 60..130 (там, где должен быть Profile и enum'ы) ---"
sed -n '60,130p' "$F" | awk '{ printf "%4d| %s\n", 59+NR, $0 }'
