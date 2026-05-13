#!/usr/bin/env bash
# Sanity regression with live watchdog per-app (4 apps separately).
# Location: /opt/menugen/backend/scripts/regress_606_sanity_live.sh
# Run: bash /opt/menugen/backend/scripts/regress_606_sanity_live.sh 2>&1 | tee /tmp/regress_606_sanity_live.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"

run_app() {
  local app="$1"
  local log="/tmp/_sanity_${app}_$(date +%s).log"

  echo
  echo "===================================================================="
  echo "Regression apps/${app}/ — start ($(date +%H:%M:%S))"
  echo "===================================================================="

  (
    start=$(date +%s)
    while sleep 30; do
      [ -f "$log" ] || continue
      now=$(date +%s); elapsed=$(( now - start ))
      passed=$(grep -cE "PASSED" "$log" 2>/dev/null || echo 0)
      failed=$(grep -cE "FAILED" "$log" 2>/dev/null || echo 0)
      printf "[watchdog %ds] passed=%s failed=%s\n" "$elapsed" "$passed" "$failed"
      last=$(tail -1 "$log" 2>/dev/null | head -c 200)
      echo "  └─ last: $last"
    done
  ) &
  WD=$!

  set +e
  $COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
    pytest "apps/${app}/" -v --tb=short -p no:cacheprovider --maxfail=10 \
    2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  set -e

  kill "$WD" 2>/dev/null || true
  wait "$WD" 2>/dev/null || true

  echo
  echo "apps/${app}/ — done ($(date +%H:%M:%S)), exit=$rc"
  grep -E "passed|failed|error" "$log" | tail -2 || true
}

run_app diary
run_app subscriptions
run_app menu
run_app fridge

echo
echo "===================================================================="
echo "ALL SANITY REGRESSIONS — done"
echo "===================================================================="
