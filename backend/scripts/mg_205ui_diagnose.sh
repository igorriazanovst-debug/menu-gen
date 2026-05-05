#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_diagnose.sh
# Разведка перед MG-205-UI: backend Profile/audit, web ProfilePage/Family, mobile profile/family
set -euo pipefail

ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
OUT=/tmp/mg_205ui_diag_$TS.txt

echo "=== MG-205-UI DIAGNOSE @ $TS ===" | tee "$OUT"

dump() {
  local label="$1"; shift
  echo "" | tee -a "$OUT"
  echo "===== $label =====" | tee -a "$OUT"
  "$@" 2>&1 | tee -a "$OUT" || true
}

# ---------- git ----------
dump "git status (root)" bash -c "cd $ROOT && git status --short"
dump "git log -5"        bash -c "cd $ROOT && git log --oneline -5"

# ---------- backend: Profile model ----------
dump "users/models.py: ProfileTargetAudit + targets_meta" \
  bash -c "grep -nE 'class Profile|class ProfileTargetAudit|targets_meta|target_g|fiber_target|calorie_target|TARGET_FIELDS' $ROOT/backend/apps/users/models.py | head -80"

dump "users/models.py (FULL)" cat $ROOT/backend/apps/users/models.py

# ---------- backend: nutrition / fill_profile_targets ----------
dump "users/nutrition.py / services/" bash -c "ls -la $ROOT/backend/apps/users/ | grep -E 'nutrition|services' && find $ROOT/backend/apps/users -name '*.py' | xargs grep -l 'fill_profile_targets\|calculate_targets' 2>/dev/null"

for f in $ROOT/backend/apps/users/nutrition.py $ROOT/backend/apps/users/services/nutrition_calc.py; do
  if [ -f "$f" ]; then dump "DUMP $f" cat "$f"; fi
done

# ---------- backend: serializers ----------
dump "users/serializers.py" cat $ROOT/backend/apps/users/serializers.py
dump "family/serializers.py" cat $ROOT/backend/apps/family/serializers.py

# ---------- backend: views + urls ----------
dump "users/views.py" cat $ROOT/backend/apps/users/views.py
dump "users/urls.py"  cat $ROOT/backend/apps/users/urls.py
dump "family/views.py" cat $ROOT/backend/apps/family/views.py
dump "family/urls.py"  cat $ROOT/backend/apps/family/urls.py

# ---------- backend: permissions ----------
for f in $ROOT/backend/apps/family/permissions.py $ROOT/backend/apps/users/permissions.py; do
  if [ -f "$f" ]; then dump "DUMP $f" cat "$f"; fi
done

# ---------- backend: миграции для MG-205 ----------
dump "users migrations (последние 10)" bash -c "ls -la $ROOT/backend/apps/users/migrations/ | tail -12"

# ---------- web: types + ProfilePage + Family ----------
dump "web types/index.ts (Profile/UserProfile/Family)" \
  bash -c "grep -nE 'targets_meta|target_g|fiber_target|calorie_target|UserProfile|Profile |MealPlan|FamilyMember' $ROOT/web/menugen-web/src/types/index.ts | head -80"

dump "web types/index.ts (FULL)" cat $ROOT/web/menugen-web/src/types/index.ts

dump "web pages/Profile structure" bash -c "find $ROOT/web/menugen-web/src/pages/Profile -maxdepth 3 -type f 2>/dev/null"
for f in $(find $ROOT/web/menugen-web/src/pages/Profile -maxdepth 3 -type f 2>/dev/null); do
  dump "DUMP $f" cat "$f"
done

dump "web Family pages structure" bash -c "find $ROOT/web/menugen-web/src/pages/Family -maxdepth 3 -type f 2>/dev/null"
for f in $(find $ROOT/web/menugen-web/src/pages/Family -maxdepth 3 -type f 2>/dev/null); do
  dump "DUMP $f" cat "$f"
done

dump "web api/ files" bash -c "ls $ROOT/web/menugen-web/src/api/ 2>/dev/null"
for f in $ROOT/web/menugen-web/src/api/users.ts $ROOT/web/menugen-web/src/api/family.ts $ROOT/web/menugen-web/src/api/profile.ts $ROOT/web/menugen-web/src/api/client.ts; do
  if [ -f "$f" ]; then dump "DUMP $f" cat "$f"; fi
done

# ---------- mobile: profile + family ----------
dump "mobile core/widgets/macro_pill.dart" cat $ROOT/mobile/menugen_app/lib/core/widgets/macro_pill.dart 2>/dev/null

dump "mobile profile_screen.dart" cat $ROOT/mobile/menugen_app/lib/features/profile/screens/profile_screen.dart 2>/dev/null

dump "mobile family_screen.dart"  cat $ROOT/mobile/menugen_app/lib/features/family/screens/family_screen.dart 2>/dev/null

dump "mobile dio_api_client.dart" cat $ROOT/mobile/menugen_app/lib/core/api/dio_api_client.dart 2>/dev/null
dump "mobile api_client.dart"     cat $ROOT/mobile/menugen_app/lib/core/api/api_client.dart 2>/dev/null

# ---------- БД ----------
dump "db: ProfileTargetAudit columns" bash -c "
  cd $ROOT && docker compose -f docker-compose.yml exec -T backend python manage.py shell -c \"
from django.db import connection
with connection.cursor() as c:
    c.execute(\\\"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name LIKE '%target_audit%' OR table_name LIKE '%profile_target%' ORDER BY table_name, ordinal_position\\\")
    for r in c.fetchall(): print(r)
\" 2>/dev/null
"

dump "db: users_profile columns" bash -c "
  cd $ROOT && docker compose -f docker-compose.yml exec -T backend python manage.py shell -c \"
from django.db import connection
with connection.cursor() as c:
    c.execute(\\\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users_profile' ORDER BY ordinal_position\\\")
    for r in c.fetchall(): print(r)
\" 2>/dev/null
"

echo ""
echo "=== DONE: $OUT ==="
ls -la "$OUT"
