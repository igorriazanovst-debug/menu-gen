#!/usr/bin/env bash
# MG-201 frontend tsc --noEmit (на хосте)
set -euo pipefail

WEB_ROOT="/opt/menugen/web/menugen-web"
cd "${WEB_ROOT}"

echo "=== node / npm versions ==="
node --version 2>/dev/null || { echo "ERROR: node не установлен на хосте"; exit 1; }
npm --version 2>/dev/null || { echo "ERROR: npm не установлен на хосте"; exit 1; }
echo

if [ ! -d node_modules ]; then
  echo "⚠️ node_modules нет — ставлю зависимости (npm ci)"
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
fi

echo "=== tsc --noEmit ==="
set +e
npx --no-install tsc --noEmit
RC=$?
set -e

echo
if [ $RC -eq 0 ]; then
  echo "✅ tsc --noEmit прошёл"
else
  echo "❌ tsc вернул код ${RC}"
fi
exit $RC
