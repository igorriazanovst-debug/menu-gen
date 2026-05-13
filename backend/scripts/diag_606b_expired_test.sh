#!/usr/bin/env bash
# DIAG: точная сигнатура test_expired_premium_403 для последующей замены
# Расположение: /opt/menugen/backend/scripts/diag_606b_expired_test.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606b_expired_test.sh

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
TEST="${ROOT}/backend/apps/diary/tests/test_mg_605c_permissions.py"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. Найти строку test_expired_premium_403"
grep -n "test_expired_premium" "$TEST"

hr "2. Показать блок (40 строк вокруг)"
awk '/def test_expired_premium/{p=1} p{print NR": "$0; n++; if(n>=30) exit}' "$TEST"

hr "3. cat -A на блок (видимые escape-символы)"
START=$(grep -n "def test_expired_premium" "$TEST" | head -1 | cut -d: -f1)
if [ -n "$START" ]; then
  END=$((START + 14))
  sed -n "${START},${END}p" "$TEST" | cat -A
fi

hr "4. Хэш блока (для подтверждения, что файл не модифицирован)"
md5sum "$TEST"
wc -l "$TEST"

echo
echo "=== diag finished ==="
