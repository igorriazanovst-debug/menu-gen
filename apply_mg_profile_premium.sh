#!/usr/bin/env bash
# MG-profile-premium: применить через python-эдиторы (без git apply).
#
# Файлы в /opt/menugen перед запуском:
#   - apply_mg_profile_premium.sh   (этот файл)
#   - edit_serializer.py
#   - edit_mobile.py
#   - test_mg_profile_premium.py
#   - premium_badge.dart
#
# bash apply_mg_profile_premium.sh

set -euo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
MOBILE="${ROOT}/mobile/menugen_app"

cd "$ROOT"

# На случай если уже есть мусор от предыдущей попытки patch-варианта
rm -f \
  "${ROOT}/01_backend_serializer.patch" \
  "${ROOT}/02_mobile_cubit.patch" \
  "${ROOT}/03_mobile_auth_bloc.patch" \
  "${ROOT}/04_mobile_main.patch" \
  "${ROOT}/05_mobile_profile_screen.patch" \
  "${ROOT}/06_mobile_cubit_tests.patch"

echo "[1/5] copy backend test"
mkdir -p "${BACKEND}/apps/users/tests"
cp "${ROOT}/test_mg_profile_premium.py" "${BACKEND}/apps/users/tests/test_mg_profile_premium.py"

echo "[2/5] copy mobile premium_badge.dart"
mkdir -p "${MOBILE}/lib/core/premium"
cp "${ROOT}/premium_badge.dart" "${MOBILE}/lib/core/premium/premium_badge.dart"

echo "[3/5] edit backend serializers.py"
python3 "${ROOT}/edit_serializer.py"

echo "[4/5] edit mobile sources"
python3 "${ROOT}/edit_mobile.py"

echo "[5/5] cleanup uploaded artifacts"
rm -f \
  "${ROOT}/edit_serializer.py" \
  "${ROOT}/edit_mobile.py" \
  "${ROOT}/test_mg_profile_premium.py" \
  "${ROOT}/premium_badge.dart"

echo
echo "===== applied. Run tests: ====="
echo "  docker compose exec -T backend pytest apps/users/tests/test_mg_profile_premium.py -v"
echo "  cd ${MOBILE} && flutter test test/premium_gate_cubit_test.dart"
