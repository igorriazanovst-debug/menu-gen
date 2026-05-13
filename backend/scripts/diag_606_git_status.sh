#!/usr/bin/env bash
# DIAG: current git status and changed files before MG-606 commits.
# Location: /opt/menugen/backend/scripts/diag_606_git_status.sh
# Run: bash /opt/menugen/backend/scripts/diag_606_git_status.sh 2>&1 | tee /tmp/diag_606_git_status.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"

hr() { printf '\n========== %s ==========\n' "$1"; }

cd "$ROOT"

hr "1. branch + recent commits"
git rev-parse --abbrev-ref HEAD
git log --oneline -5

hr "2. git status"
git status

hr "3. Changed files list (untracked + modified)"
git status --porcelain

hr "4. .gitignore content (sanity)"
cat .gitignore 2>/dev/null | head -30 || true

hr "5. Per-file split planned"
echo "MG-606.A (helpers + permission + tests):"
echo "  M  backend/apps/subscriptions/permissions.py"
echo "  ?? backend/apps/subscriptions/tests/__init__.py"
echo "  ?? backend/apps/subscriptions/tests/test_mg_606a_premium_helpers.py"
echo
echo "MG-606.B (diary migration to IsFamilyPremiumOrReadOnly):"
echo "  M  backend/apps/diary/views.py"
echo "  M  backend/apps/diary/tests/test_mg_605c_permissions.py"
echo "  ?? backend/apps/diary/tests/test_mg_606b_premium_or_readonly.py"
echo
echo "MG-606.C (menu/fridge/notifications gate + tests):"
echo "  M  backend/apps/menu/views.py"
echo "  M  backend/apps/menu/tests/test_menu.py"
echo "  M  backend/apps/menu/tests/test_mg_301.py"
echo "  M  backend/apps/menu/tests/test_mg_601_integration.py"
echo "  M  backend/apps/menu/tests/test_mg_602_views.py"
echo "  M  backend/apps/menu/tests/test_mg_605a_mode.py"
echo "  ?? backend/apps/menu/tests/test_mg_606c_premium_gate.py"
echo "  M  backend/apps/fridge/views.py"
echo "  M  backend/apps/fridge/tests/test_fridge.py"
echo "  ?? backend/apps/fridge/tests/test_mg_606c_premium_gate.py"
echo "  M  backend/apps/notifications/views.py"
echo "  ?? backend/apps/notifications/tests/test_mg_606c_premium_gate.py"
echo
echo "Untracked scripts in /opt/menugen/backend/scripts/ — exclude from MG-606."

hr "6. Are scripts tracked?"
git ls-files backend/scripts/ 2>/dev/null | head
echo "---"
git status backend/scripts/ 2>/dev/null

echo
echo "=== diag finished ==="
