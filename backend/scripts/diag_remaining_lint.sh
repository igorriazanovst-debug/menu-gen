#!/usr/bin/env bash
# DIAG: посмотреть КОНТЕКСТ E402 и F841 перед добавлением noqa.
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. apps/menu/generator.py:875-885 — E402 контекст"
sed -n '870,890p' "${BACKEND}/apps/menu/generator.py"

hr "2. apps/specialists/views.py:25-32 — E402 контекст"
sed -n '20,35p' "${BACKEND}/apps/specialists/views.py"

hr "3. apps/menu/tests/test_menu.py:180-195 — E402 контекст"
sed -n '175,200p' "${BACKEND}/apps/menu/tests/test_menu.py"

hr "4. apps/fridge/tests/test_fridge.py:155-170 — E402 контекст"
sed -n '150,170p' "${BACKEND}/apps/fridge/tests/test_fridge.py"

hr "5. apps/menu/tests/test_mg_605a_mode.py:355-372 — E402 контекст"
sed -n '355,372p' "${BACKEND}/apps/menu/tests/test_mg_605a_mode.py"

hr "6. apps/users/audit.py:45-65 — F841 'pta' контекст"
sed -n '40,70p' "${BACKEND}/apps/users/audit.py"

hr "7. apps/menu/tests/test_mg_304.py:148-156 — E501 контекст"
sed -n '148,158p' "${BACKEND}/apps/menu/tests/test_mg_304.py"

hr "8. apps/users/tests/test_mg_205.py:1-15 — E501 контекст"
sed -n '1,15p' "${BACKEND}/apps/users/tests/test_mg_205.py"

echo
echo "=== done ==="
