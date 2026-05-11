#!/usr/bin/env bash
# MG-603 diag: apps/recipes/serializers.py 77% → 85%+
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg603_diag_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  MG-603 DIAGNOSE  ($TS)"
echo "=========================================="

echo
echo "--- [1] apps/recipes/serializers.py — структура ---"
$COMPOSE exec -T backend bash -lc '
  echo "--- LOC ---"
  wc -l apps/recipes/serializers.py
  echo
  echo "--- классы и методы ---"
  grep -nE "^class |^\s{4}def |^def " apps/recipes/serializers.py
'

echo
echo "--- [2] Полный текст serializers.py с номерами строк ---"
$COMPOSE exec -T backend cat -n apps/recipes/serializers.py

echo
echo "--- [3] coverage report --show-missing ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing | grep -E "recipes/serializers|TOTAL"
'

echo
echo "--- [4] Существующие тесты apps/recipes/tests ---"
$COMPOSE exec -T backend bash -lc '
  ls -1 apps/recipes/tests/
  echo
  for f in apps/recipes/tests/test_*.py; do
    [ -f "$f" ] || continue
    echo "=== $f ==="
    grep -nE "def test_|class Test" "$f"
    echo
  done
'

echo
echo "--- [5] apps/recipes/urls.py ---"
$COMPOSE exec -T backend cat apps/recipes/urls.py

echo
echo "--- [6] apps/recipes/views.py (для понимания, через какие endpoint бить сериализаторы) ---"
$COMPOSE exec -T backend cat -n apps/recipes/views.py

echo
echo "--- [7] apps/recipes/models.py — поля Recipe (что валидируется) ---"
$COMPOSE exec -T backend bash -lc '
  grep -nE "= models\." apps/recipes/models.py | head -50
'

echo
echo "--- [8] Существующий conftest для recipes (если есть) ---"
$COMPOSE exec -T backend bash -lc '
  cat apps/recipes/tests/conftest.py 2>/dev/null || echo "(нет)"
  cat apps/recipes/conftest.py 2>/dev/null || echo "(нет apps/recipes/conftest.py)"
'

echo
echo "=========================================="
echo "  MG-603 DIAG DONE → $OUT"
echo "=========================================="
