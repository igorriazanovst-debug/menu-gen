#!/usr/bin/env bash
# Diagnostic: Flutter mobile app baseline before MG-204 mobile work (chat 31)
# Usage: bash /opt/menugen/backend/scripts/diag_mobile_baseline.sh 2>&1 | tee /tmp/diag_mobile_baseline.out
set -u

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"
LIB="${MOB}/lib"

hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }
sub() { echo; echo "--- $* ---"; }

hdr "0. Environment"
echo "date:   $(date -Is)"
echo "host:   $(hostname)"
echo "whoami: $(whoami)"
echo "pwd:    $(pwd)"

hdr "1. Mobile project exists?"
if [ ! -d "${MOB}" ]; then
  echo "!!! ${MOB} does not exist — abort."
  exit 0
fi
ls -la "${MOB}" | head -30

hdr "2. Git state of mobile (if it's a separate repo or part of monorepo)"
sub "is there .git in /opt/menugen?"
[ -d "${ROOT}/.git" ] && echo "  yes (monorepo)" || echo "  no"
sub "is there .git in mobile/menugen_app?"
[ -d "${MOB}/.git" ] && echo "  yes (separate repo)" || echo "  no"
sub "git log --oneline -20 (from monorepo root, mobile path)"
cd "${ROOT}" 2>/dev/null && git log --oneline -20 -- mobile/menugen_app/ 2>/dev/null || echo "  n/a"
sub "git status (mobile path)"
cd "${ROOT}" 2>/dev/null && git status -s -- mobile/menugen_app/ 2>/dev/null || echo "  n/a"
sub "current branch + HEAD"
cd "${ROOT}" 2>/dev/null && git rev-parse --abbrev-ref HEAD 2>/dev/null
cd "${ROOT}" 2>/dev/null && git rev-parse --short HEAD 2>/dev/null

hdr "3. pubspec.yaml (full)"
[ -f "${MOB}/pubspec.yaml" ] && cat "${MOB}/pubspec.yaml" || echo "  pubspec.yaml MISSING"

hdr "4. pubspec.lock — key versions"
if [ -f "${MOB}/pubspec.lock" ]; then
  echo "  size: $(wc -l < "${MOB}/pubspec.lock") lines"
  grep -E "^  (flutter_bloc|dio|drift|go_router|flutter_secure_storage|shared_preferences|connectivity_plus):" "${MOB}/pubspec.lock" 2>/dev/null || echo "  (no top-level deps matched — check format)"
else
  echo "  pubspec.lock MISSING (deps never resolved?)"
fi

hdr "5. Flutter SDK presence"
which flutter 2>/dev/null && flutter --version 2>/dev/null | head -5 || echo "  flutter not in PATH"
ls -la /opt/flutter*/bin/flutter 2>/dev/null || true
ls -la "${HOME}/flutter/bin/flutter" 2>/dev/null || true

hdr "6. lib/ structure"
sub "directories (depth 3)"
find "${LIB}" -maxdepth 3 -type d 2>/dev/null | sort
sub "feature folders (depth 2)"
find "${LIB}/features" -maxdepth 1 -type d 2>/dev/null | sort
sub "file count per feature"
for d in "${LIB}/features"/*/; do
  [ -d "$d" ] || continue
  n=$(find "$d" -type f -name "*.dart" 2>/dev/null | wc -l)
  printf "  %-30s %4d .dart files\n" "$(basename "$d")" "$n"
done

hdr "7. ApiClient — full source"
APICLIENT=$(find "${LIB}" -type f -name "api_client.dart" 2>/dev/null | head -1)
if [ -n "${APICLIENT}" ]; then
  echo "  path: ${APICLIENT}"
  echo "  lines: $(wc -l < "${APICLIENT}")"
  echo "----------------------------------------------------------------"
  cat "${APICLIENT}"
  echo "----------------------------------------------------------------"
else
  echo "  api_client.dart NOT FOUND"
fi

hdr "8. How is 403 / Premium currently handled?"
sub "grep for 403 / forbidden / premium / paywall / subscription in lib/"
grep -rEn "403|forbidden|Forbidden|premium|Premium|paywall|Paywall|subscription|Subscription" "${LIB}" 2>/dev/null | head -60 || echo "  no matches"

hdr "9. Diary feature — current state"
sub "diary files"
find "${LIB}/features/diary" -type f -name "*.dart" 2>/dev/null | sort
sub "diary_bloc.dart"
[ -f "${LIB}/features/diary/bloc/diary_bloc.dart" ] && cat "${LIB}/features/diary/bloc/diary_bloc.dart" || echo "  not found"
sub "diary models (anywhere referenced)"
grep -rEn "DiaryEntry|planned_menu_item|is_eaten|import-from-menu|importFromMenu|member_id|memberId" "${LIB}/features/diary" 2>/dev/null | head -40 || echo "  no matches"
sub "diary_screen.dart (head 80)"
[ -f "${LIB}/features/diary/screens/diary_screen.dart" ] && head -80 "${LIB}/features/diary/screens/diary_screen.dart" || echo "  not found"

hdr "10. Menu feature — current state (for premium gate context)"
sub "menu files"
find "${LIB}/features/menu" -type f -name "*.dart" 2>/dev/null | sort
sub "menu_bloc.dart — error handling around 403?"
[ -f "${LIB}/features/menu/bloc/menu_bloc.dart" ] && grep -nE "catch|DioException|statusCode|403" "${LIB}/features/menu/bloc/menu_bloc.dart" || echo "  not found"

hdr "11. Fridge / Notifications features"
sub "fridge files"
find "${LIB}/features/fridge" -type f -name "*.dart" 2>/dev/null | sort
sub "notifications feature exists?"
ls -la "${LIB}/features/notifications" 2>/dev/null || echo "  no notifications feature"

hdr "12. Subscription / Profile screens — premium awareness"
sub "subscription feature exists?"
find "${LIB}" -type d -iname "*subscription*" 2>/dev/null
find "${LIB}" -type f -iname "*subscription*" 2>/dev/null
sub "profile_screen.dart — premium fields?"
PROF=$(find "${LIB}" -type f -name "profile_screen.dart" 2>/dev/null | head -1)
if [ -n "${PROF}" ]; then
  grep -nE "premium|Premium|plan|subscription|expires" "${PROF}" 2>/dev/null || echo "  no premium fields in profile screen"
else
  echo "  profile_screen.dart not found"
fi

hdr "13. main.dart and dependency injection"
sub "main.dart (full)"
[ -f "${LIB}/main.dart" ] && cat "${LIB}/main.dart" || echo "  main.dart MISSING"

hdr "14. App router"
ROUTER=$(find "${LIB}" -type f -name "app_router.dart" 2>/dev/null | head -1)
[ -n "${ROUTER}" ] && cat "${ROUTER}" || echo "  app_router.dart NOT FOUND"

hdr "15. Tests"
sub "test/ structure"
find "${MOB}/test" -type f -name "*.dart" 2>/dev/null | sort
sub "test count"
echo "  total: $(find "${MOB}/test" -type f -name "*.dart" 2>/dev/null | wc -l)"

hdr "16. Local DB — drift schema"
sub "drift files"
find "${LIB}/core/db" -type f 2>/dev/null | sort
sub "diary table in drift?"
grep -rEn "diary|Diary" "${LIB}/core/db" 2>/dev/null | head -20 || echo "  no matches"

hdr "17. Base URL configuration"
sub "where is baseUrl defined?"
grep -rEn "baseUrl|BASE_URL|apiUrl|API_URL" "${LIB}" 2>/dev/null | head -20

hdr "18. assets and platform"
sub "android/app/build.gradle key bits"
grep -E "applicationId|minSdk|targetSdk|versionName|versionCode" "${MOB}/android/app/build.gradle" 2>/dev/null
sub "android permissions"
cat "${MOB}/android/app/src/main/AndroidManifest.xml" 2>/dev/null | head -40

hdr "19. Build runner artifacts — generated code present?"
sub "*.g.dart and *.freezed.dart in lib/"
find "${LIB}" -type f \( -name "*.g.dart" -o -name "*.freezed.dart" \) 2>/dev/null | head -30
echo "  total generated: $(find "${LIB}" -type f \( -name "*.g.dart" -o -name "*.freezed.dart" \) 2>/dev/null | wc -l)"

hdr "20. Recent backend-impacting commits in mobile (last 30)"
cd "${ROOT}" 2>/dev/null && git log --oneline -30 -- mobile/menugen_app/ 2>/dev/null | head -30 || echo "  n/a"

hdr "DONE"
echo "Output saved to /tmp/diag_mobile_baseline.out (if you used `| tee`)"
