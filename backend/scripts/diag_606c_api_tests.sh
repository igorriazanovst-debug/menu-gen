#!/usr/bin/env bash
# DIAG: какие тесты menu/fridge/notifications ходят в API (нужно Premium),
# а какие — pure-python (не нужно). Плюс — какие фикстуры/Family.create
# используются.
# Расположение: /opt/menugen/backend/scripts/diag_606c_api_tests.sh
# Запуск: bash /opt/menugen/backend/scripts/diag_606c_api_tests.sh 2>&1 | tee /tmp/diag_606c_api_tests.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"

hr() { printf '\n========== %s ==========\n' "$1"; }

for app in menu fridge notifications; do
  hr "=== Приложение: ${app} ==="

  for f in "${BACKEND}/apps/${app}/tests/"test_*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    api_calls=$(grep -cE "client\.(get|post|patch|put|delete)\(" "$f" || echo 0)
    auth_calls=$(grep -cE "force_authenticate|force_login" "$f" || echo 0)
    family_creates=$(grep -cE "Family\.objects\.create" "$f" || echo 0)
    sub_creates=$(grep -cE "Subscription\.objects\.create" "$f" || echo 0)
    api_v1_diary=$(grep -cE "/api/v1/" "$f" || echo 0)

    printf "\n--- %s ---\n" "$name"
    printf "  API calls (client.{get,post,...}): %s\n" "$api_calls"
    printf "  force_authenticate:                %s\n" "$auth_calls"
    printf "  Family.objects.create:             %s\n" "$family_creates"
    printf "  Subscription.objects.create:       %s\n" "$sub_creates"
    printf "  /api/v1/ paths:                    %s\n" "$api_v1_diary"

    if [ "$api_calls" -gt 0 ] || [ "$auth_calls" -gt 0 ]; then
      printf "  >>> ТРЕБУЕТ Premium (API-тесты)\n"
      echo "  --- API endpoints, которые ходят:"
      grep -nE "client\.(get|post|patch|put|delete)\(['\"]/api/" "$f" | head -10
    else
      printf "  >>> pure-python (Premium не нужен)\n"
    fi
  done
done

hr "Детально: menu/tests/test_mg_302.py — что внутри (нет Family.create)"
head -30 "${BACKEND}/apps/menu/tests/test_mg_302.py"

hr "Детально: menu/tests/test_mg_303.py — что внутри"
head -30 "${BACKEND}/apps/menu/tests/test_mg_303.py"

hr "Детально: menu/tests/test_mg_502_503.py — что внутри"
head -30 "${BACKEND}/apps/menu/tests/test_mg_502_503.py"

hr "Детально: menu/tests/test_mg_604_exceptions.py — что внутри"
head -30 "${BACKEND}/apps/menu/tests/test_mg_604_exceptions.py"

hr "Детально: menu/tests/test_mg_604_portions.py — что внутри"
head -30 "${BACKEND}/apps/menu/tests/test_mg_604_portions.py"

hr "notifications/test_tasks.py — суть тестов (Celery-таски или API?)"
grep -nE "def test_|client\.|send_notification|@pytest|^class" "${BACKEND}/apps/notifications/tests/test_tasks.py" | head -40

hr "fridge/test_fridge.py — список тестов"
grep -nE "def test_|client\." "${BACKEND}/apps/fridge/tests/test_fridge.py" | head -30

echo
echo "=== diag finished ==="
