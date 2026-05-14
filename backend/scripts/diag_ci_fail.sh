#!/usr/bin/env bash
# Quick diagnostic before fixing CI failures.
set -u
MOB="/opt/menugen/mobile/menugen_app"

hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }

hdr "1. family_bloc_test.dart — current"
sed -n '40,60p' "${MOB}/test/family_bloc_test.dart"

hdr "2. family_bloc_test.dart — was this test broken before patch? (check on previous HEAD)"
cd /opt/menugen
echo "Looking at the file at commit ad9453f (before our patch):"
git show ad9453f:mobile/menugen_app/test/family_bloc_test.dart 2>/dev/null | sed -n '40,60p' || echo "  file not present"

hdr "3. widget_test.dart — current"
cat "${MOB}/test/widget_test.dart"

hdr "4. widget_test.dart — at previous HEAD"
git show ad9453f:mobile/menugen_app/test/widget_test.dart 2>/dev/null || echo "  file not present"

hdr "5. fridge_screen.dart — what events does it call?"
grep -n "FridgeBloc\|FridgeItemDeleted\|FridgeDeleteRequested\|FridgeAddRequested\|FridgeItemAdded\|FridgeLoadRequested" "${MOB}/lib/features/fridge/screens/fridge_screen.dart"

hdr "6. fridge_screen.dart — full (it's small)"
cat "${MOB}/lib/features/fridge/screens/fridge_screen.dart"

hdr "7. OLD fridge_bloc events — what existed in the backed-up version?"
BAK_DIR="$(ls -td ${MOB}/.bak-* 2>/dev/null | head -1)"
echo "backup dir: ${BAK_DIR}"
[ -f "${BAK_DIR}/lib/features/fridge/bloc/fridge_bloc.dart" ] && \
  grep -n "class Fridge.*Event\|class Fridge.*Requested\|class Fridge.*Added\|class Fridge.*Deleted" "${BAK_DIR}/lib/features/fridge/bloc/fridge_bloc.dart"

hdr "8. previous flutter_ci run (#25) — was widget_test/family_bloc_test already failing?"
# We don't have CI logs locally; we just look at git log of those test files
git log --oneline mobile/menugen_app/test/widget_test.dart 2>/dev/null | head -5
echo "---"
git log --oneline mobile/menugen_app/test/family_bloc_test.dart 2>/dev/null | head -5
echo "---"
git log --oneline mobile/menugen_app/lib/features/fridge/screens/fridge_screen.dart 2>/dev/null | head -5

hdr "DONE"
