#!/usr/bin/env bash
# DIAG-2: точечные доуточнения перед патчем MG-profile-premium
# Расположение: /opt/menugen/backend/scripts/diag_profile_premium2.sh
# Запуск:        bash /opt/menugen/backend/scripts/diag_profile_premium2.sh 2>&1 | tee /tmp/diag_profile_premium2.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
MOBILE="${ROOT}/mobile/menugen_app"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── BACKEND ────────────────────────────────────────────────────────────────

hr "B10. UserMeSerializer + UserMeUpdateSerializer ПОЛНОСТЬЮ"
sed -n '185,260p' "${BACKEND}/apps/users/serializers.py"

hr "B11. Импорты в users/serializers.py (топ файла)"
sed -n '1,15p' "${BACKEND}/apps/users/serializers.py"

hr "B12. Where IsFamilyPremiumOrReadOnly is used (find all importers)"
grep -rnE "from apps\.subscriptions\.permissions import|from apps\.subscriptions import permissions" "${BACKEND}/apps" | head -20

# ─── MOBILE ─────────────────────────────────────────────────────────────────

hr "M9. auth_bloc.dart ПОЛНОСТЬЮ — что делается с /users/me/ response"
cat "${MOBILE}/lib/features/auth/bloc/auth_bloc.dart"

hr "M10. auth_state.dart — есть ли модель User"
cat "${MOBILE}/lib/features/auth/bloc/auth_state.dart"

hr "M11. profile_screen.dart — как парсится ответ /users/me/ и какие поля показываются"
sed -n '1,120p' "${MOBILE}/lib/features/profile/screens/profile_screen.dart"

hr "M12. PremiumGateCubit — остаток файла после строки 80"
sed -n '80,200p' "${MOBILE}/lib/core/premium/premium_gate_cubit.dart"

hr "M13. main.dart — как именно создаётся PremiumGateCubit и где attachErrorStream"
cat "${MOBILE}/lib/main.dart"

hr "M14. Существующие тесты в test/ — для шаблона"
ls -la "${MOBILE}/test/" 2>/dev/null
echo "---"
grep -l "PremiumGate\|premium_gate" "${MOBILE}/test/"*.dart 2>/dev/null

hr "M15. premium_gate_cubit_test.dart — шаблон существующего теста"
cat "${MOBILE}/test/premium_gate_cubit_test.dart" 2>/dev/null | head -80

echo
echo "=== diag-2 finished ==="
