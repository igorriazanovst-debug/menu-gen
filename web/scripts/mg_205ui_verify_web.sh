#!/bin/bash
# /opt/menugen/web/scripts/mg_205ui_verify_web.sh
# MG-205-UI: TS-проверка через build (без -e, чтобы видеть всю картину).
set -uo pipefail

ROOT=/opt/menugen
WEB=$ROOT/web/menugen-web
TS=$(date +%Y%m%d_%H%M%S)
LOG=/tmp/mg_205ui_web_verify_${TS}.log

echo "=== MG-205-UI web verify @ $TS ===" | tee "$LOG"

cd "$WEB"

echo "" | tee -a "$LOG"
echo "── 1) tsc --noEmit (через npx) ──" | tee -a "$LOG"
npx --no-install tsc --noEmit 2>&1 | tee -a "$LOG" | tail -60
echo "  exit=$?" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "── 2) ESLint только новых/изменённых файлов ──" | tee -a "$LOG"
npx --no-install eslint \
  src/components/profile/TargetField.tsx \
  src/components/family/FamilyMemberEditModal.tsx \
  src/pages/Profile/ProfilePage.tsx \
  src/api/users.ts \
  src/api/family.ts \
  src/types/index.ts 2>&1 | tee -a "$LOG" | tail -50
echo "  exit=$?" | tee -a "$LOG"

echo ""
echo "=== Log: $LOG ==="
