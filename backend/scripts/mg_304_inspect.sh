#!/bin/bash
set -uo pipefail
F="/opt/menugen/backend/apps/menu/generator.py"
echo "=== все def методы ==="
grep -nE "^[[:space:]]+def " "$F"
echo
echo "=== как используется hard_exclude ==="
grep -nE "hard_exclude|allowed|_filter|_pick_for_role" "$F"
