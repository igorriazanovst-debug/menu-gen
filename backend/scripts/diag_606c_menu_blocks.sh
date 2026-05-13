#!/usr/bin/env bash
# DIAG: точные блоки кода для вставки Premium-подписки в фикстуры menu/tests/
# Расположение: /opt/menugen/backend/scripts/diag_606c_menu_blocks.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606c_menu_blocks.sh 2>&1 | tee /tmp/diag_606c_menu_blocks.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }
dump_range() {
  local f="$1"; local s="$2"; local e="$3"
  echo "--- $f [$s..$e] ---"
  sed -n "${s},${e}p" "$f" | nl -ba -v "$s"
}

# ── 1. menu/tests/test_menu.py — setup ────────────────────────────────────
hr "menu/test_menu.py — структура (imports + setup)"
sed -n '1,40p' "${BACKEND}/apps/menu/tests/test_menu.py" | nl -ba

# ── 2. menu/tests/test_mg_301.py — setup_full + 3 inline Family ───────────
hr "menu/test_mg_301.py — imports"
sed -n '1,25p' "${BACKEND}/apps/menu/tests/test_mg_301.py" | nl -ba

hr "menu/test_mg_301.py — setup_full (стр ~40-80)"
sed -n '40,80p' "${BACKEND}/apps/menu/tests/test_mg_301.py" | nl -ba -v 40

hr "menu/test_mg_301.py — 3 inline Family.create (стр 125-180)"
sed -n '125,180p' "${BACKEND}/apps/menu/tests/test_mg_301.py" | nl -ba -v 125

# ── 3. menu/tests/test_mg_601_integration.py — фабрика на стр.55 ──────────
hr "menu/test_mg_601_integration.py — imports + фабрика (стр 1-75)"
sed -n '1,75p' "${BACKEND}/apps/menu/tests/test_mg_601_integration.py" | nl -ba

# ── 4. menu/tests/test_mg_602_views.py — фабрика + 2 inline ──────────────
hr "menu/test_mg_602_views.py — imports + фабрика (стр 1-115)"
sed -n '1,115p' "${BACKEND}/apps/menu/tests/test_mg_602_views.py" | nl -ba

# ── 5. menu/tests/test_mg_605a_mode.py — 2 фикстуры ──────────────────────
hr "menu/test_mg_605a_mode.py — imports + 2 фикстуры (стр 1-100)"
sed -n '1,100p' "${BACKEND}/apps/menu/tests/test_mg_605a_mode.py" | nl -ba

echo
echo "=== diag finished ==="
