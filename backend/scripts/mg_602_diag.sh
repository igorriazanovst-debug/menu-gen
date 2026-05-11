#!/usr/bin/env bash
# MG-602 diagnose: точечная инвентаризация покрытия apps/menu/views.py
# Цель: понять какие строки/ветви не покрыты и какие фикстуры уже есть.
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg602_diagnose_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  MG-602 DIAGNOSE  ($TS)"
echo "=========================================="

echo
echo "--- [1] apps/menu/views.py — общая структура ---"
$COMPOSE exec -T backend bash -lc '
  echo "--- LOC ---"
  wc -l apps/menu/views.py
  echo
  echo "--- классы и методы ---"
  grep -nE "^class |^\s{4}def |^def " apps/menu/views.py
  echo
  echo "--- helper functions (top-level def) ---"
  grep -nE "^def " apps/menu/views.py
'

echo
echo "--- [2] coverage report --show-missing для apps/menu/views.py ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  echo "--- coverage report полный ---"
  coverage report --rcfile=.coveragerc --show-missing
'

echo
echo "--- [3] Полный текст views.py (для анализа missing lines) ---"
$COMPOSE exec -T backend cat -n apps/menu/views.py

echo
echo "--- [4] Существующие тесты, которые бьют views.py ---"
$COMPOSE exec -T backend bash -lc '
  for f in apps/menu/tests/test_*.py; do
    [ -f "$f" ] || continue
    echo "=== $f ==="
    grep -nE "def test_|client\.(get|post|patch|delete|put)|reverse\(" "$f" | head -30
    echo
  done
'

echo
echo "--- [5] Фикстуры из test_menu.py (первые 80 строк — setup) ---"
$COMPOSE exec -T backend sed -n '1,80p' apps/menu/tests/test_menu.py

echo
echo "--- [6] Фикстуры из test_mg_601_integration.py (как создаётся окружение) ---"
$COMPOSE exec -T backend sed -n '1,100p' apps/menu/tests/test_mg_601_integration.py

echo
echo "--- [7] urls.py (повторно — для маппинга url-name → view) ---"
$COMPOSE exec -T backend cat apps/menu/urls.py

echo
echo "--- [8] serializers.py — что валидируется (для негативных кейсов) ---"
$COMPOSE exec -T backend cat apps/menu/serializers.py

echo
echo "--- [9] Permission-helpers и edge-cases ---"
$COMPOSE exec -T backend grep -nE "_get_family|_can_delete_menu|_collect_allergens|_check_allergens|_recipe_calories|_menu_snapshot|HTTP_403|HTTP_404|HTTP_400" apps/menu/views.py

echo
echo "--- [10] conftest.py (есть ли готовые фикстуры) ---"
$COMPOSE exec -T backend bash -lc '
  echo "--- /app/conftest.py ---"
  cat /app/conftest.py 2>/dev/null || echo "(нет)"
  echo
  echo "--- apps/menu/tests/conftest.py ---"
  cat apps/menu/tests/conftest.py 2>/dev/null || echo "(нет)"
  echo
  echo "--- apps/menu/conftest.py ---"
  cat apps/menu/conftest.py 2>/dev/null || echo "(нет)"
'

echo
echo "=========================================="
echo "  MG-602 DIAGNOSE DONE → $OUT"
echo "=========================================="
