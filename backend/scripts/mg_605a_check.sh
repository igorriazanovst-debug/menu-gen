#!/usr/bin/env bash
# MG-605.A check: проверка patch'a (без повторного применения)
set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "[1] Django check (загрузка моделей и URL)"
$COMPOSE exec -T backend python manage.py check 2>&1 | tail -10
echo

echo "[2] py_compile проверка четырёх файлов"
$COMPOSE exec -T backend python -m py_compile \
  apps/menu/portions.py \
  apps/menu/serializers.py \
  apps/menu/generator.py \
  apps/menu/views.py && echo "  OK: все 4 файла компилируются"
echo

echo "[3] Маркеры 605A в исходниках"
$COMPOSE exec -T backend bash -c '
  echo "--- portions.py ---"
  grep -n "MG_605A" apps/menu/portions.py || echo "  НЕТ"
  echo "--- serializers.py ---"
  grep -n "MG_605A" apps/menu/serializers.py || echo "  НЕТ"
  echo "--- generator.py ---"
  grep -n "MG_605A" apps/menu/generator.py || echo "  НЕТ"
  echo "--- views.py ---"
  grep -n "MG_605A" apps/menu/views.py || echo "  НЕТ"
'
echo

echo "[4] Регрессионные тесты apps/menu (быстрый прогон)"
$COMPOSE exec -T backend pytest apps/menu/ -q --tb=short 2>&1 | tail -25
echo

echo "[5] Регрессионные тесты apps/recipes (быстрый прогон)"
$COMPOSE exec -T backend pytest apps/recipes/ -q --tb=short 2>&1 | tail -10
echo

echo "=== DONE 605.A check ==="
