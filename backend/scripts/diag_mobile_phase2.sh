#!/usr/bin/env bash
# Phase 2 diag: read full sources we need before patching diary + global 403 handling.
# Usage: bash /opt/menugen/backend/scripts/diag_mobile_phase2.sh 2>&1 | tee /tmp/diag_mobile_phase2.out
set -u

LIB="/opt/menugen/mobile/menugen_app/lib"
TST="/opt/menugen/mobile/menugen_app/test"

hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }
dump() {
  local f="$1"
  if [ -f "$f" ]; then
    echo "### FILE: $f ($(wc -l < "$f") lines)"
    echo "----------------------------------------------------------------"
    cat "$f"
    echo
    echo "----------------------------------------------------------------"
  else
    echo "### FILE: $f — MISSING"
  fi
}

hdr "1. core/api/dio_api_client.dart"
dump "${LIB}/core/api/dio_api_client.dart"

hdr "2. core/api/token_storage.dart"
dump "${LIB}/core/api/token_storage.dart"

hdr "3. core/config/app_config.dart"
dump "${LIB}/core/config/app_config.dart"

hdr "4. core/db/app_database.dart"
dump "${LIB}/core/db/app_database.dart"

hdr "5. core/db/tables.dart"
dump "${LIB}/core/db/tables.dart"

hdr "6. core/sync/sync_service.dart"
dump "${LIB}/core/sync/sync_service.dart"

hdr "7. core/widgets/main_shell.dart"
dump "${LIB}/core/widgets/main_shell.dart"

hdr "8. features/diary/bloc/diary_event.dart"
dump "${LIB}/features/diary/bloc/diary_event.dart"

hdr "9. features/diary/bloc/diary_state.dart"
dump "${LIB}/features/diary/bloc/diary_state.dart"

hdr "10. features/diary/screens/diary_screen.dart (FULL)"
dump "${LIB}/features/diary/screens/diary_screen.dart"

hdr "11. features/menu/bloc/menu_bloc.dart"
dump "${LIB}/features/menu/bloc/menu_bloc.dart"

hdr "12. features/menu/bloc/menu_event.dart"
dump "${LIB}/features/menu/bloc/menu_event.dart"

hdr "13. features/menu/bloc/menu_state.dart"
dump "${LIB}/features/menu/bloc/menu_state.dart"

hdr "14. features/menu/screens/menu_screen.dart"
dump "${LIB}/features/menu/screens/menu_screen.dart"

hdr "15. features/family/bloc/family_bloc.dart"
dump "${LIB}/features/family/bloc/family_bloc.dart"

hdr "16. features/auth/bloc/auth_bloc.dart"
dump "${LIB}/features/auth/bloc/auth_bloc.dart"

hdr "17. test/diary_bloc_test.dart"
dump "${TST}/diary_bloc_test.dart"

hdr "18. test/menu_bloc_test.dart"
dump "${TST}/menu_bloc_test.dart"

hdr "19. ApiException — does it exist anywhere?"
grep -rn "ApiException" "${LIB}" 2>/dev/null || echo "  none"

hdr "20. Any existing 'BasePremiumAwareBloc' / interceptor pattern?"
grep -rn "Interceptor\|interceptors\|onError\|DioError\|DioException" "${LIB}" 2>/dev/null | head -40

hdr "DONE"
