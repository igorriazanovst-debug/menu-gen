#!/usr/bin/env bash
set -u
ROOT="/opt/menugen"

echo "### Полные urls.py всех приложений (ищем users/me):"
find "${ROOT}/backend" -name "urls.py" -path "*/apps/*" -exec sh -c '
  echo "--- $1"; nl -ba "$1"
' _ {} \;

echo
echo "### Корневой urls.py проекта:"
find "${ROOT}/backend" -name "urls.py" -not -path "*/apps/*" -exec sh -c '
  echo "--- $1"; nl -ba "$1"
' _ {} \;

echo
echo "### users/views.py (целиком):"
find "${ROOT}/backend" -path '*/users/views.py' -exec nl -ba {} \;

echo
echo "### users/serializers.py — UserMeUpdateSerializer + ProfileSerializer (с 80 по 200):"
F=$(find "${ROOT}/backend" -path '*/users/serializers.py' | head -1)
[ -n "$F" ] && sed -n '80,220p' "$F" | nl -ba

echo
echo "### web ProfilePage.tsx (целиком):"
PP="${ROOT}/web/menugen-web/src/pages/Profile/ProfilePage.tsx"
[ -f "$PP" ] && nl -ba "$PP" || echo "нет"

echo
echo "### web api/users.ts:"
find "${ROOT}/web/menugen-web/src" -name "users.ts" -exec nl -ba {} \;

echo
echo "### web api клиент base path:"
find "${ROOT}/web/menugen-web/src/api" -name "client.ts" -o -name "axios*.ts" -o -name "index.ts" 2>/dev/null | head -5 | xargs -I{} sh -c 'echo "--- {}"; nl -ba "{}"'

echo
echo "DONE"
