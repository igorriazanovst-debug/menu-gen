#!/usr/bin/env bash
# DIAG: actual URL of ProductSearchView in fridge
# Location: /opt/menugen/backend/scripts/diag_606c2_fridge_urls.sh
# Run: bash /opt/menugen/backend/scripts/diag_606c2_fridge_urls.sh

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. fridge/urls.py — all routes"
cat -n "${BACKEND}/apps/fridge/urls.py"

hr "2. ProductSearchView usage in existing tests"
grep -rn "product\|fridge-product\|ProductSearchView" "${BACKEND}/apps/fridge/" --include='*.py'

echo
echo "=== diag finished ==="
