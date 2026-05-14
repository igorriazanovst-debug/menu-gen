#!/usr/bin/env bash
# Phase 3 diag: verify backend contract for diary endpoints, premium 403 shape, and stats schema.
# Mobile patches must match reality, not assumption.
# Usage: bash /opt/menugen/backend/scripts/diag_backend_contract.sh 2>&1 | tee /tmp/diag_backend_contract.out
set -u

BE="/opt/menugen/backend"
APP="${BE}/menugen"

hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }
dump() {
  local f="$1"
  local lines="${2:-200}"
  if [ -f "$f" ]; then
    echo "### FILE: $f ($(wc -l < "$f") lines, showing first ${lines})"
    echo "----------------------------------------------------------------"
    head -n "$lines" "$f"
    echo "----------------------------------------------------------------"
  else
    echo "### FILE: $f — MISSING"
  fi
}

hdr "1. Diary URL routes — actual paths"
sub_routes() {
  grep -rEn "diary|Diary" "${APP}" --include="*.py" -l 2>/dev/null | grep -E "urls\.py|router\.py" | sort -u
}
sub_routes
echo "---"
echo "Looking for URL patterns mentioning diary:"
grep -rEn "diary" "${APP}" --include="urls.py" 2>/dev/null
echo "---"
echo "Looking for ViewSet registrations / path() for diary:"
grep -rEn "DiaryViewSet|DiaryView|diary_router|import-from-menu|import_from_menu" "${APP}" --include="*.py" 2>/dev/null | head -40

hdr "2. Diary serializers — field names & types"
DIARY_SER=$(find "${APP}" -type f -name "serializers.py" | xargs grep -l "Diary" 2>/dev/null | head -5)
for f in $DIARY_SER; do
  echo "--- $f ---"
  grep -n -A 40 "class.*Diary.*Serializer" "$f" 2>/dev/null | head -100
done

hdr "3. Diary model — planned_menu_item, is_eaten fields"
DIARY_MOD=$(find "${APP}" -type f -name "models.py" | xargs grep -l "class.*Diary" 2>/dev/null | head -5)
for f in $DIARY_MOD; do
  echo "--- $f ---"
  grep -n -A 30 "class.*Diary" "$f" 2>/dev/null
done

hdr "4. Diary stats endpoint — actual shape"
echo "Looking for /stats/ or stats action in diary viewsets:"
grep -rEn "stats" "${APP}" --include="*.py" 2>/dev/null | grep -iE "diary|@action" | head -30

hdr "5. Premium gate — how does backend return 403?"
echo "Looking for permission classes / 403 / PremiumRequired / IsPremium:"
grep -rEn "IsPremium|PremiumRequired|premium_required|premium_only|@premium|permission_classes" "${APP}" --include="*.py" 2>/dev/null | head -40

hdr "6. Premium error response shape — error_code field?"
echo "Looking for error_code / PermissionDenied custom message in views/permissions:"
grep -rEn "error_code|errorCode|PermissionDenied|raise.*Permission" "${APP}" --include="*.py" 2>/dev/null | head -40

hdr "7. Permissions module — full source"
PERM_FILES=$(find "${APP}" -type f -name "permissions.py" 2>/dev/null)
for f in $PERM_FILES; do
  dump "$f" 300
done

hdr "8. Diary views — full source of the main viewset"
DIARY_VIEWS=$(find "${APP}" -type f -name "views.py" | xargs grep -l "Diary" 2>/dev/null | head -3)
for f in $DIARY_VIEWS; do
  dump "$f" 500
done

hdr "9. User /users/me/ response — premium fields"
ME_VIEW=$(grep -rEn "class.*MeView\|users/me\|def me\b" "${APP}" --include="*.py" 2>/dev/null | head -5)
echo "$ME_VIEW"
echo "---"
echo "User serializer — premium-related fields:"
USER_SER=$(find "${APP}" -type f -name "serializers.py" | xargs grep -l "UserSerializer\|class.*User.*Serializer" 2>/dev/null | head -3)
for f in $USER_SER; do
  echo "--- $f ---"
  grep -n -A 30 "class.*User.*Serializer" "$f" 2>/dev/null | head -60
done
echo "---"
echo "Subscription / plan models:"
grep -rEn "subscription_plan|premium_until|is_premium|plan_type|trial_ends" "${APP}" --include="models.py" 2>/dev/null | head -30

hdr "10. import-from-menu — does endpoint exist?"
grep -rEn "import.from.menu|import_from_menu" "${APP}" --include="*.py" 2>/dev/null

hdr "11. Recent backend commits about diary / premium (last 50)"
cd /opt/menugen 2>/dev/null && git log --oneline -50 -- backend/ 2>/dev/null | grep -iE "diary|premium|MG-605|MG-606|MG-204|MG-606|gate" | head -30

hdr "12. DRF settings — DEFAULT_RENDERER / EXCEPTION_HANDLER"
SETTINGS=$(find "${APP}" -type f -name "settings*.py" 2>/dev/null | head -5)
for f in $SETTINGS; do
  echo "--- $f (REST_FRAMEWORK block) ---"
  grep -n -A 20 "REST_FRAMEWORK" "$f" 2>/dev/null
done

hdr "DONE"
