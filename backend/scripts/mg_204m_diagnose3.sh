#!/usr/bin/env bash
# MG-204 mobile — разведка: какой endpoint редактирует свой профиль
set -u
ROOT="/opt/menugen"

echo "### users/urls.py:"
find "${ROOT}/backend" -path '*/users/urls.py' -exec nl -ba {} \;

echo
echo "### users/views.py — ищем UpdateAPIView / patch / users/me:"
find "${ROOT}/backend" -path '*/users/views.py' -exec grep -nE "UpdateAPIView|patch|users/me|me/profile|profile/update|class .*View" {} \;

echo
echo "### users/serializers.py — Profile* классы:"
find "${ROOT}/backend" -path '*/users/serializers.py' -exec grep -nE "class .*Serializer|fields = |meal_plan_type|protein_target|calorie_target" {} \;

echo
echo "### web: api/users.ts (как фронт обновляет профиль):"
find "${ROOT}/web" -name "users.ts" -path "*/api/*" -exec nl -ba {} \;

echo
echo "### web: ProfilePage — как сохраняет:"
PP="${ROOT}/web/menugen-web/src/pages/Profile/ProfilePage.tsx"
[ -f "$PP" ] && grep -nE "patch|api\.|axios|client\.|usersApi|/users|/me" "$PP" | head -30 || echo "  ProfilePage.tsx нет"

echo
echo "### Реальный JSON GET /users/me (требует JWT — пропускаю если нет logging)"
echo "  выполни вручную при необходимости"

echo
echo "DONE"
