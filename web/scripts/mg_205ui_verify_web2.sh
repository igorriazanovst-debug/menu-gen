#!/bin/bash
# /opt/menugen/web/scripts/mg_205ui_verify_web2.sh
# MG-205-UI web verify v2: прямой вызов локальных бинарей.
set -uo pipefail

WEB=/opt/menugen/web/menugen-web
TS=$(date +%Y%m%d_%H%M%S)
LOG=/tmp/mg_205ui_web_verify2_${TS}.log

cd "$WEB"

echo "=== MG-205-UI web verify v2 @ $TS ===" | tee "$LOG"

echo "" | tee -a "$LOG"
echo "── 1) tsc --noEmit (direct) ──" | tee -a "$LOG"
./node_modules/.bin/tsc --noEmit 2>&1 | tee -a "$LOG"
TSC_EXIT=${PIPESTATUS[0]}
echo "  tsc exit=$TSC_EXIT" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "── 2) eslint новых/изменённых файлов ──" | tee -a "$LOG"
./node_modules/.bin/eslint \
  src/components/profile/TargetField.tsx \
  src/components/family/FamilyMemberEditModal.tsx \
  src/pages/Profile/ProfilePage.tsx \
  src/api/users.ts \
  src/api/family.ts \
  src/types/index.ts 2>&1 | tee -a "$LOG"
LINT_EXIT=${PIPESTATUS[0]}
echo "  eslint exit=$LINT_EXIT" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== Summary: tsc=$TSC_EXIT, eslint=$LINT_EXIT ===" | tee -a "$LOG"
echo "Log: $LOG"
