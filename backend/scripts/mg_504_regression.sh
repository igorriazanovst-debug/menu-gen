#!/usr/bin/env bash
# MG-504 regression: users + menu
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== users tests ==="
$COMPOSE exec -T backend pytest apps/users/ -v --tb=short
echo
echo "=== menu tests ==="
$COMPOSE exec -T backend pytest apps/menu/ -v --tb=short
echo
echo "=== family tests (если есть) ==="
$COMPOSE exec -T backend pytest apps/family/ -v --tb=short || echo "(no family tests / failed)"
