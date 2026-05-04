#!/usr/bin/env bash
# MG-205 prep step 2: дамп nutrition.py + Profile.save() + audit-helpers
# Read-only.
# Запуск: bash /opt/menugen/backend/scripts/mg_205_diagnose3.sh

set -u
BACKEND="/opt/menugen/backend"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. apps/users/nutrition.py — полный дамп"
cat -n "${BACKEND}/apps/users/nutrition.py"

hr "2. apps/users/models.py — секция Profile.save()"
grep -nE 'def save|fill_profile_targets|MG_2|class Profile' "${BACKEND}/apps/users/models.py"

hr "3. apps/users/signals.py — текущий"
cat -n "${BACKEND}/apps/users/signals.py"

hr "4. apps/users/serializers.py — структура"
grep -nE 'class |fields\s*=|Meta:|target' "${BACKEND}/apps/users/serializers.py"

hr "5. apps/family/serializers.py — структура (после MG-203)"
grep -nE 'class |fields\s*=|Meta:|target|MG_203' "${BACKEND}/apps/family/serializers.py"

hr "6. apps/users/views.py — UserMeView подробно"
grep -nE 'class UserMeView|serializer_class|def perform_update|def get_object|def update|def patch|def get_serializer_context' "${BACKEND}/apps/users/views.py"

hr "7. apps/family/views.py — где правка профиля FamilyMember"
grep -nE 'class |def perform_update|def update|def get_serializer|profile|Profile' "${BACKEND}/apps/family/views.py" | head -40

echo
echo "=== prep done ==="
