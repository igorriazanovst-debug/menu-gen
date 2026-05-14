#!/usr/bin/env bash
# Phase 3c: dump the exact source mobile must match.
# Usage: bash /opt/menugen/backend/scripts/diag_backend_dump.sh 2>&1 | tee /tmp/diag_backend_dump.out
set -u

BE="/opt/menugen/backend"
hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }
dump() {
  local f="$1"
  local n="${2:-99999}"
  if [ -f "$f" ]; then
    echo "### FILE: $f ($(wc -l < "$f") lines, showing up to $n)"
    echo "----------------------------------------------------------------"
    head -n "$n" "$f"
    echo "----------------------------------------------------------------"
  else
    echo "### FILE: $f — MISSING"
  fi
}

hdr "1. diary/urls.py"
dump "${BE}/apps/diary/urls.py"

hdr "2. diary/models.py"
dump "${BE}/apps/diary/models.py"

hdr "3. diary/serializers.py"
dump "${BE}/apps/diary/serializers.py"

hdr "4. diary/permissions.py"
dump "${BE}/apps/diary/permissions.py"

hdr "5. diary/views.py"
dump "${BE}/apps/diary/views.py"

hdr "6. subscriptions/permissions.py"
dump "${BE}/apps/subscriptions/permissions.py"

hdr "7. config/urls.py — api version + diary mount"
dump "${BE}/config/urls.py"

hdr "8. users serializer for /users/me/ + premium fields shape"
dump "${BE}/apps/users/serializers.py"
echo
echo "### users/views.py (head 200)"
dump "${BE}/apps/users/views.py" 200

hdr "9. users/urls/ (subfolder)"
ls -la "${BE}/apps/users/urls" 2>/dev/null
for f in "${BE}/apps/users/urls"/*.py; do dump "$f"; done

hdr "10. subscriptions/models.py — plan / premium_until / has_ever_had_premium fields"
dump "${BE}/apps/subscriptions/models.py"

hdr "11. menu/serializers.py (relevant for import-from-menu MenuItem shape)"
dump "${BE}/apps/menu/serializers.py" 300

hdr "12. DRF settings block — exception handler / renderers"
grep -n -A 30 "REST_FRAMEWORK" "${BE}/config/settings.py" 2>/dev/null

hdr "DONE"
