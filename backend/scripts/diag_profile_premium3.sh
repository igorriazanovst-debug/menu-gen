#!/usr/bin/env bash
# DIAG-3: финальные доуточнения перед патчем
# Запуск: bash /opt/menugen/backend/scripts/diag_profile_premium3.sh 2>&1 | tee /tmp/diag_profile_premium3.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "B13. permissions.py — has_active_premium + has_ever_had_premium + get_user_family"
sed -n '1,80p' "${BACKEND}/apps/subscriptions/permissions.py"

hr "B14. openapi/schema generation — есть ли drf-spectacular CLI команда"
grep -rE "spectacular|openapi" "${BACKEND}/manage.py" 2>/dev/null
grep -rE "SPECTACULAR_SETTINGS|spectacular" "${BACKEND}/menugen/settings.py" 2>/dev/null | head -10
echo "---"
ls "${BACKEND}/schema.yml" "${BACKEND}/openapi.yaml" "${BACKEND}/openapi.yml" 2>/dev/null
echo "---"
find "${BACKEND}" -maxdepth 3 -name "schema.yml" -o -name "openapi.yaml" -o -name "openapi.yml" 2>/dev/null | head -5

hr "B15. CI — генерация schema (что делает workflow)"
grep -nE "spectacular|schema" "${ROOT}/.github/workflows/"*.yml 2>/dev/null | head -20

hr "B16. pytest конфиг + где живёт conftest"
ls "${BACKEND}/conftest.py" "${BACKEND}/pyproject.toml" "${BACKEND}/pytest.ini" "${BACKEND}/setup.cfg" 2>/dev/null
echo "---"
grep -nE "DJANGO_SETTINGS_MODULE|pytest" "${BACKEND}/pytest.ini" "${BACKEND}/setup.cfg" "${BACKEND}/pyproject.toml" 2>/dev/null | head -10

hr "B17. Existing test_mg_606a — шаблон с Family/Subscription/Plan фикстурами"
sed -n '1,80p' "${BACKEND}/apps/subscriptions/tests/test_mg_606a_premium_helpers.py" 2>/dev/null

echo
echo "=== diag-3 finished ==="
