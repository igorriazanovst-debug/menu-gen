#!/usr/bin/env bash
# DIAG2: точная информация для apply Premium gate
# Запуск: bash /opt/menugen/backend/scripts/diag_premium_gate2.sh 2>&1 | tee /tmp/diag_premium_gate2.log

set -u
ROOT="/opt/menugen"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. menu/views.py — импорты"
sed -n '1,40p' "${BACKEND}/apps/menu/views.py"

hr "2. fridge/views.py — импорты"
sed -n '1,30p' "${BACKEND}/apps/fridge/views.py"

hr "3. notifications/views.py — целиком (маленький)"
cat -n "${BACKEND}/apps/notifications/views.py"

hr "4. diary/views.py — импорты + permission_classes"
sed -n '1,30p' "${BACKEND}/apps/diary/views.py"
echo "..."
grep -n "permission_classes" "${BACKEND}/apps/diary/views.py"

hr "5. Subscription.Status — все значения"
grep -nE "class Status|=\s*['\"]" "${BACKEND}/apps/subscriptions/models.py" | head -30

hr "6. Существующий тест test_mg_605c_permissions.py — какие тесты ожидают 403 от GET без Premium"
grep -nE "get\(.*\)\.status_code\s*==\s*403|test_no_premium" "${BACKEND}/apps/diary/tests/test_mg_605c_permissions.py" | head -30

hr "7. Тесты menu/fridge/notifications — есть ли уже фикстуры с Premium"
grep -rnE "premium|Premium|PREMIUM|SubscriptionPlan|Subscription\(" \
  "${BACKEND}/apps/menu/tests/" "${BACKEND}/apps/fridge/tests/" "${BACKEND}/apps/notifications/tests/" \
  2>/dev/null | head -30

hr "8. Subscription и SubscriptionPlan — фабрики/фикстуры в conftest.py"
find "${BACKEND}/apps" -name "conftest.py" -exec echo "--- {} ---" \; -exec cat {} \;

hr "9. Размер test_diary.py и test_mg_605c_permissions.py"
wc -l "${BACKEND}/apps/diary/tests/test_diary.py" "${BACKEND}/apps/diary/tests/test_mg_605c_permissions.py" "${BACKEND}/apps/diary/tests/test_mg_605b_planned_eaten.py"

hr "10. Все вызовы _premium_family / _make_family_with_premium / setup в diary тестах"
grep -nE "_premium_family|_make_family_with_premium|def setup|Premium|Subscription" \
  "${BACKEND}/apps/diary/tests/test_diary.py" | head -30
grep -nE "_premium_family|_make_family_with_premium|def setup|Premium|Subscription" \
  "${BACKEND}/apps/diary/tests/test_mg_605b_planned_eaten.py" | head -30

echo
echo "=== diag2 finished ==="
