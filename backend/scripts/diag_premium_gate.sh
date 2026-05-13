#!/usr/bin/env bash
# DIAG: текущее покрытие Premium gate по приложениям (read-only)
# Запуск: bash /opt/menugen/backend/scripts/diag_premium_gate.sh 2>&1 | tee /tmp/diag_premium_gate.log

set -u
ROOT="/opt/menugen"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "0. Бранч и коммит"
git -C "$ROOT" rev-parse --abbrev-ref HEAD
git -C "$ROOT" log --oneline -3

hr "1. Структура apps/"
ls -1 "${BACKEND}/apps/" | grep -v __pycache__

hr "2. Где уже используется IsFamilyPremium (импорты)"
grep -rn "IsFamilyPremium" "${BACKEND}/apps/" --include='*.py' | grep -v __pycache__ | grep -v "/tests/"

hr "3. Где импортируется has_active_premium / get_user_family"
grep -rnE "has_active_premium|get_user_family" "${BACKEND}/apps/" --include='*.py' | grep -v __pycache__ | grep -v "/tests/"

hr "4. permissions.IsAuthenticated в каждом приложении (счётчик)"
for app in $(ls -1 "${BACKEND}/apps/" | grep -v __pycache__); do
  views="${BACKEND}/apps/${app}/views.py"
  [ -f "$views" ] || continue
  cnt_views=$(grep -cE "class\s+\w+(View|ViewSet)" "$views" || echo 0)
  cnt_isauth=$(grep -cE "IsAuthenticated" "$views" || echo 0)
  cnt_isprem=$(grep -cE "IsFamilyPremium" "$views" || echo 0)
  printf "  %-15s views=%-3s IsAuthenticated=%-3s IsFamilyPremium=%-3s\n" \
    "$app" "$cnt_views" "$cnt_isauth" "$cnt_isprem"
done

hr "5. URL-неймспейсы (что реально подключено в API)"
grep -nE "path\(.+include\(" "${BACKEND}/config/urls.py" 2>/dev/null || \
grep -nE "path\(.+include\(" "${BACKEND}/menugen/urls.py" 2>/dev/null

hr "6. ТЗ-фичи Premium: что считается платным в коде"
grep -rnE "premium|Premium|PREMIUM" "${BACKEND}/apps/" --include='*.py' \
  | grep -v __pycache__ | grep -v "/tests/" | grep -v "/migrations/" | head -40

hr "7. SubscriptionPlan — какие поля квот/лимитов"
grep -nE "class SubscriptionPlan|=\s*models\.|max_|limit|premium" \
  "${BACKEND}/apps/subscriptions/models.py" 2>/dev/null | head -40

hr "8. Существующие тесты с Premium / IsFamilyPremium"
grep -rln "IsFamilyPremium\|has_active_premium\|premium" "${BACKEND}/apps/" --include='test_*.py' | head

hr "9. Views по приложениям (полный список классов)"
for app in menu recipes specialists fridge notifications social sync subscriptions payments family users; do
  views="${BACKEND}/apps/${app}/views.py"
  [ -f "$views" ] || continue
  printf "\n--- %s/views.py ---\n" "$app"
  grep -nE "^class\s+\w+(View|ViewSet)" "$views"
done

hr "10. permission_classes — все строки по каждому приложению"
for app in menu recipes specialists fridge notifications social sync; do
  views="${BACKEND}/apps/${app}/views.py"
  [ -f "$views" ] || continue
  printf "\n--- %s/views.py ---\n" "$app"
  grep -nE "permission_classes\s*=" "$views"
done

hr "11. Все pytest-маркеры/файлы тестов по приложениям"
${COMPOSE} exec -T backend bash -c "find apps -name 'test_*.py' -not -path '*/__pycache__/*' | sort"

echo
echo "=== diag_premium_gate finished ==="
