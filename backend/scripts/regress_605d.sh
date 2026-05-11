#!/usr/bin/env bash
# MG-605.D regress: полный прогон всех приложений с прогрессом по тестам
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "================================================================"
echo "  FULL REGRESS — все приложения, verbose, durations top-10"
echo "================================================================"
echo

$COMPOSE exec -T backend pytest apps/ \
    -v \
    --tb=short \
    --durations=10 \
    -p no:cacheprovider \
    2>&1 | tail -200

echo
echo "================================================================"
echo "  REGRESS DONE"
echo "================================================================"
