#!/usr/bin/env bash
# Регресс menu с прогресс-индикацией каждый 30 сек + per-test вывод
# Расположение: /opt/menugen/backend/scripts/regress_menu_live.sh
# Запуск: bash /opt/menugen/backend/scripts/regress_menu_live.sh 2>&1 | tee /tmp/regress_menu_live.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
LOG=/tmp/_menu_regress_$(date +%s).log

echo "===================================================================="
echo "Регресс apps/menu/ — старт ($(date +%H:%M:%S))"
echo "===================================================================="
echo "Параметры:"
echo "  -v             : per-test строки"
echo "  --tb=short     : короткий traceback"
echo "  -p no:cacheprovider : отключить кэш"
echo "  PYTHONUNBUFFERED=1  : без буферизации stdout python"
echo "  --maxfail=15   : остановиться после 15 ошибок"
echo

# Watchdog — печатает каждые 30 сек, сколько прошло и сколько тестов закрыто
(
  start=$(date +%s)
  while sleep 30; do
    if [ ! -f "$LOG" ]; then continue; fi
    now=$(date +%s)
    elapsed=$(( now - start ))
    passed=$(grep -cE "PASSED" "$LOG" 2>/dev/null || echo 0)
    failed=$(grep -cE "FAILED" "$LOG" 2>/dev/null || echo 0)
    errors=$(grep -cE "ERROR " "$LOG" 2>/dev/null || echo 0)
    printf "[watchdog %ds] passed=%s failed=%s errors=%s\n" \
      "$elapsed" "$passed" "$failed" "$errors"
    # самая свежая строка
    last=$(tail -1 "$LOG" 2>/dev/null | head -c 200)
    echo "  └─ last: $last"
  done
) &
WD=$!

# Сам запуск тестов
set +e
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/menu/ -v --tb=short -p no:cacheprovider --maxfail=20 \
  2>&1 | tee "$LOG"
RC=$?
set -e

kill "$WD" 2>/dev/null || true
wait "$WD" 2>/dev/null || true

echo
echo "===================================================================="
echo "Регресс apps/menu/ — финиш ($(date +%H:%M:%S)), exit=$RC"
echo "===================================================================="
echo "Итоги:"
grep -E "passed|failed|error" "$LOG" | tail -3 || true
echo
echo "Полный лог: $LOG"
