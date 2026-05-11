#!/usr/bin/env bash
# MG-605.D regress (live progress):
#   - pytest без буферизации stdout (-s, PYTHONUNBUFFERED=1, stdbuf)
#   - watchdog в фоне: каждые 30с пишет heartbeat
#   - таймаут на тест (pytest-timeout если есть; иначе SIGTERM от bash через timeout)
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
START_TS=$(date +%s)
LOG=/tmp/regress_605d_live.out
HEARTBEAT_LOG=/tmp/regress_605d_heartbeat.out
: > "$LOG"
: > "$HEARTBEAT_LOG"

echo "================================================================"
echo "  FULL REGRESS — live progress mode"
echo "  log file:        $LOG"
echo "  heartbeat file:  $HEARTBEAT_LOG"
echo "================================================================"
echo

# ── Watchdog: фоновый процесс, который каждые 30с пишет heartbeat ──
(
  while true; do
    sleep 30
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TS))
    MIN=$((ELAPSED / 60))
    SEC=$((ELAPSED % 60))
    # последняя строка из лога pytest
    LAST=$(tail -1 "$LOG" 2>/dev/null | tr -d '\r' | cut -c1-120)
    MSG="[heartbeat] alive — elapsed ${MIN}m${SEC}s — last: ${LAST}"
    echo "$MSG"
    echo "$MSG" >> "$HEARTBEAT_LOG"
  done
) &
WATCHDOG_PID=$!

# Гарантированное убийство watchdog при выходе
cleanup() {
  kill "$WATCHDOG_PID" 2>/dev/null || true
  wait "$WATCHDOG_PID" 2>/dev/null || true
  END_TS=$(date +%s)
  TOTAL=$((END_TS - START_TS))
  echo
  echo "================================================================"
  echo "  REGRESS DONE — total $((TOTAL / 60))m$((TOTAL % 60))s"
  echo "================================================================"
}
trap cleanup EXIT INT TERM

# ── Pytest без буферизации: ──
# -s              : не захватывать stdout (видим print)
# -v              : имя каждого теста
# --tb=short
# -p no:cacheprovider
# PYTHONUNBUFFERED=1 + stdbuf -oL -eL : построчная буферизация на стороне python
# unbuffer (если есть) или stdbuf — для docker exec
$COMPOSE exec -T \
    -e PYTHONUNBUFFERED=1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    backend \
    stdbuf -oL -eL \
    pytest apps/ \
        -v -s \
        --tb=short \
        -p no:cacheprovider \
        --color=no \
    2>&1 | tee "$LOG"
