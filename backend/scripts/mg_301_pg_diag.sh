#!/usr/bin/env bash
# MG-301 diagnose pg: какой POSTGRES_USER/DB/PASSWORD реально настроены
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
COMPOSE="${PROJECT_ROOT}/docker-compose.yml"

echo "=== PG CREDENTIALS DIAGNOSE ==="
echo

echo "[1] docker compose ps"
docker compose -f "${COMPOSE}" ps
echo

echo "[2] env переменные db-сервиса"
docker compose -f "${COMPOSE}" exec -T db printenv 2>&1 | grep -E "^POSTGRES" || true
echo

echo "[3] env переменные backend-сервиса"
docker compose -f "${COMPOSE}" exec -T backend printenv 2>&1 | grep -E "^(POSTGRES|DATABASE|DB_)" || true
echo

echo "[4] список ролей в pg"
docker compose -f "${COMPOSE}" exec -T db psql -U postgres -c "\du" 2>&1 || true
echo

echo "[5] список баз в pg"
docker compose -f "${COMPOSE}" exec -T db psql -U postgres -c "\l" 2>&1 || true
echo

echo "[6] компоуз — фрагмент db-сервиса (первые 80 строк, без пароля)"
sed -n '1,200p' "${COMPOSE}" | grep -nE "^\s*(db:|backend:|environment:|POSTGRES_|DATABASE|image:|env_file:)" || true
echo

echo "=== DONE ==="
