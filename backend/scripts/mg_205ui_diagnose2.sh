#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_diagnose2.sh
set -euo pipefail
ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
OUT=/tmp/mg_205ui_diag2_$TS.txt
echo "=== DIAG2 @ $TS ===" | tee "$OUT"
dump() { local l="$1"; shift; echo "" | tee -a "$OUT"; echo "===== $l =====" | tee -a "$OUT"; "$@" 2>&1 | tee -a "$OUT" || true; }

dump "users/audit.py"   cat $ROOT/backend/apps/users/audit.py
dump "users/signals.py" cat $ROOT/backend/apps/users/signals.py
dump "config urls"      bash -c "find $ROOT/backend -name urls.py | xargs grep -l 'users/me\|users.urls\|users/' 2>/dev/null"
dump "config/urls.py"   cat $ROOT/backend/config/urls.py 2>/dev/null
dump "ALL urls.py with users/me ref" bash -c "grep -rn 'users/me\|UserMeView\|users\.views' $ROOT/backend --include='*.py' | head -30"
dump "Spec apps available?" bash -c "ls $ROOT/backend/apps/specialists/ 2>/dev/null && cat $ROOT/backend/apps/specialists/permissions.py 2>/dev/null | head -60"
dump "tests/test_mg_205.py" cat $ROOT/backend/apps/users/tests/test_mg_205.py
dump "web auth.ts"        cat $ROOT/web/menugen-web/src/api/auth.ts
dump "web FamilyMemberEditModal" bash -c "find $ROOT/web/menugen-web/src/components/family -type f 2>/dev/null"
for f in $(find $ROOT/web/menugen-web/src/components/family -type f 2>/dev/null); do
  dump "DUMP $f" cat "$f"
done
dump "web Badge component"  cat $ROOT/web/menugen-web/src/components/ui/Badge.tsx 2>/dev/null
dump "web AppRoutes / store" bash -c "ls $ROOT/web/menugen-web/src/store/slices/ 2>/dev/null && grep -rn 'setUser\|fetchMe' $ROOT/web/menugen-web/src/store/ 2>/dev/null | head -20"
dump "mobile family bloc"   bash -c "find $ROOT/mobile/menugen_app/lib/features/family -type f"
for f in $(find $ROOT/mobile/menugen_app/lib/features/family -type f); do
  dump "DUMP $f" cat "$f"
done
echo "=== DONE: $OUT ==="
