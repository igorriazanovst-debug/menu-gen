#!/usr/bin/env bash
# MG-205 prep step 3: дамп FamilyMemberUpdateView + UserMeView + update() методов serializers
# Read-only.
set -u
BACKEND="/opt/menugen/backend"
hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. apps/users/views.py — UserMeView полностью"
sed -n '55,110p' "${BACKEND}/apps/users/views.py" | cat -n

hr "2. apps/family/views.py — FamilyMemberUpdateView полностью"
sed -n '120,200p' "${BACKEND}/apps/family/views.py" | cat -n

hr "3. apps/users/serializers.py — UserMeUpdateSerializer + ProfileSerializer полностью"
sed -n '85,170p' "${BACKEND}/apps/users/serializers.py" | cat -n

hr "4. apps/family/serializers.py — ProfileUpdateSerializer + FamilyMemberUpdateSerializer"
sed -n '83,170p' "${BACKEND}/apps/family/serializers.py" | cat -n

hr "5. apps/specialists/views.py — где IsVerifiedSpecialist"
sed -n '20,40p' "${BACKEND}/apps/specialists/views.py" | cat -n

hr "6. Импорты в apps/users/serializers.py (для контекста)"
sed -n '1,15p' "${BACKEND}/apps/users/serializers.py" | cat -n

hr "7. Импорты в apps/family/serializers.py"
sed -n '1,15p' "${BACKEND}/apps/family/serializers.py" | cat -n

echo
echo "=== prep3 done ==="
