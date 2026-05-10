#!/usr/bin/env bash
# MG-601 run coverage: pytest apps/menu + apps/recipes под coverage
# Использование:
#   bash /opt/menugen/backend/scripts/mg_601_run_coverage.sh
#   bash /opt/menugen/backend/scripts/mg_601_run_coverage.sh --html
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

WANT_HTML=0
for a in "$@"; do
  [ "$a" = "--html" ] && WANT_HTML=1
done

echo "=== MG-601 coverage run ==="

$COMPOSE exec -T backend bash -lc '
  set -eu
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=short
  echo
  echo "--- coverage report ---"
  coverage report --rcfile=.coveragerc
'

if [ "$WANT_HTML" -eq 1 ]; then
  $COMPOSE exec -T backend bash -lc '
    cd /app
    coverage html --rcfile=.coveragerc
    echo "HTML отчёт в /app/htmlcov внутри контейнера"
  '
fi

echo "=== MG-601 coverage DONE ==="
