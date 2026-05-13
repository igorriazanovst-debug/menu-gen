#!/usr/bin/env bash
# DIAG: точные сигнатуры 9 падающих тестов test_no_family/no_family_404 в test_mg_602_views.py
# Расположение: /opt/menugen/backend/scripts/diag_606c1_602_tests.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606c1_602_tests.sh 2>&1 | tee /tmp/diag_606c1_602_tests.log

set -u
F=/opt/menugen/backend/apps/menu/tests/test_mg_602_views.py

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. Все def test_*no_family* в файле"
grep -nE "def test_.*no_family|def test_list_no_family_returns_empty" "$F"

hr "2. Блок test_no_family_returns_404 (стр 222-235)"
sed -n '218,232p' "$F" | nl -ba -v 218

hr "3. Блок test_list_no_family_returns_empty (стр 250-265)"
sed -n '250,265p' "$F" | nl -ba -v 250

hr "4. Блок test_detail_no_family_returns_404 (стр 258-270)"
sed -n '258,270p' "$F" | nl -ba -v 258

hr "5. Блок test_delete_no_family_404 (стр 290-300)"
sed -n '290,305p' "$F" | nl -ba -v 290

hr "6. Блок test_quarantine_list_no_family_404 (стр 320-330)"
sed -n '320,335p' "$F" | nl -ba -v 320

hr "7. Блок test_restore_no_family_404 (стр 335-345)"
sed -n '335,350p' "$F" | nl -ba -v 335

hr "8. Блок test_swap_no_family_404 (стр 415-425)"
sed -n '413,425p' "$F" | nl -ba -v 413

hr "9. Блок test_shopping_no_family_404 (стр 552-565)"
sed -n '550,565p' "$F" | nl -ba -v 550

hr "10. Блок test_toggle_item_no_family_404 (стр 610-620)"
sed -n '608,620p' "$F" | nl -ba -v 608

echo
echo "=== diag finished ==="
