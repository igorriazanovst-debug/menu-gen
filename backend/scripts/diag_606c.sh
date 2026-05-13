#!/usr/bin/env bash
# DIAG: где в menu/fridge/notifications тестах создаётся Family — нужно
# добавить активную Premium-подписку, чтобы тесты не сломались после MG-606.C
# Расположение: /opt/menugen/backend/scripts/diag_606c.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606c.sh 2>&1 | tee /tmp/diag_606c.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. menu/tests — все файлы и строки с Family.objects.create"
for f in "${BACKEND}/apps/menu/tests/"test_*.py; do
  [ -f "$f" ] || continue
  echo
  echo "--- $f ---"
  grep -nE "Family\.objects\.create|Subscription\.objects\.create|SubscriptionPlan|setup\(|conftest|@pytest\.fixture|def family|def head|def user|def setup" "$f" | head -20
done

hr "2. fridge/tests — то же"
for f in "${BACKEND}/apps/fridge/tests/"test_*.py; do
  [ -f "$f" ] || continue
  echo
  echo "--- $f ---"
  grep -nE "Family\.objects\.create|Subscription\.objects\.create|SubscriptionPlan|setup\(|conftest|@pytest\.fixture|def family|def head|def user|def setup" "$f" | head -20
done

hr "3. notifications/tests — то же"
for f in "${BACKEND}/apps/notifications/tests/"test_*.py; do
  [ -f "$f" ] || continue
  echo
  echo "--- $f ---"
  grep -nE "Family\.objects\.create|Subscription\.objects\.create|SubscriptionPlan|setup\(|conftest|@pytest\.fixture|def family|def head|def user|def setup" "$f" | head -20
done

hr "4. Поиск conftest.py в этих приложениях"
find "${BACKEND}/apps/menu" "${BACKEND}/apps/fridge" "${BACKEND}/apps/notifications" -name "conftest.py" 2>/dev/null

hr "5. Полный листинг тестов (для оценки объёма)"
wc -l "${BACKEND}/apps/menu/tests/"test_*.py 2>/dev/null
wc -l "${BACKEND}/apps/fridge/tests/"test_*.py 2>/dev/null
wc -l "${BACKEND}/apps/notifications/tests/"test_*.py 2>/dev/null

hr "6. menu/views.py — полный список classов + методы"
grep -nE "^class\s+\w+(View|ViewSet)|^    def (get|post|patch|put|delete|create|update|destroy)" \
  "${BACKEND}/apps/menu/views.py" | head -40

hr "7. fridge/views.py — то же"
grep -nE "^class\s+\w+(View|ViewSet)|^    def (get|post|patch|put|delete|create|update|destroy)" \
  "${BACKEND}/apps/fridge/views.py"

hr "8. notifications/views.py — то же"
grep -nE "^class\s+\w+(View|ViewSet)|^    def (get|post|patch|put|delete|create|update|destroy)" \
  "${BACKEND}/apps/notifications/views.py"

hr "9. recipes/views.py — нужно понять, почему RecipeViewSet (AllowAny + IsAuthenticated)"
grep -nE "^class|permission_classes" "${BACKEND}/apps/recipes/views.py"

hr "10. Пример помощника-фикстуры в diary тестах (что переиспользуем как образец)"
sed -n '1,50p' "${BACKEND}/apps/diary/tests/test_mg_606b_premium_or_readonly.py"

echo
echo "=== diag finished ==="
