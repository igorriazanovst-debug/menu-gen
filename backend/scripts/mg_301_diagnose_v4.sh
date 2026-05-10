#!/usr/bin/env bash
# MG-301 diagnose v4
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
BACKEND="${PROJECT_ROOT}/backend"

echo "=== MG-301 DIAGNOSE v4 === $(date -Is)"
echo

echo "===== [A] apps/sync/models.py (вся структура классов и поля) ====="
if [[ -f "${BACKEND}/apps/sync/models.py" ]]; then
    grep -nE "^\s*(class |[a-z_]+\s*=\s*models\.)" "${BACKEND}/apps/sync/models.py"
    echo "  ---"
    echo "  Файл целиком: $(wc -l < "${BACKEND}/apps/sync/models.py") строк"
else
    echo "  ❌ apps/sync/models.py НЕ НАЙДЕН"
fi
echo

echo "===== [B] grep AuditLog по всем backend ====="
grep -rnE "class AuditLog\b|from apps\.sync\.models import" "${BACKEND}/apps" 2>/dev/null | head -30
echo

echo "===== [C] apps/menu/views.py — нумерация классов ====="
grep -nE "^class " "${BACKEND}/apps/menu/views.py"
echo

echo "===== [C2] apps/menu/views.py — строки 120..200 (MenuGenerateView) ====="
sed -n '120,200p' "${BACKEND}/apps/menu/views.py" | nl -ba -v 120
echo

echo "===== [D] _menu_snapshot — строки ====="
LN=$(grep -nE "^def _menu_snapshot" "${BACKEND}/apps/menu/views.py" | head -1 | cut -d: -f1)
if [[ -n "${LN:-}" ]]; then
    END=$((LN + 30))
    sed -n "${LN},${END}p" "${BACKEND}/apps/menu/views.py" | nl -ba -v "$LN"
fi
echo

echo "===== [E] apps/recipes/models.py — строки 1..120 (где Recipe + enums) ====="
sed -n '1,120p' "${BACKEND}/apps/recipes/models.py" | nl -ba
echo

echo "===== [F] conftest.py ====="
cat -n "${BACKEND}/conftest.py"
echo

echo "=== DIAGNOSE v4 DONE ==="
