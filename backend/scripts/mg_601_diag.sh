#!/usr/bin/env bash
# MG-601 diagnose: baseline coverage + инвентаризация что есть/чего нет
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== 1. Установлен ли coverage в backend ==="
$COMPOSE exec -T backend bash -c '
  pip show coverage 2>/dev/null | grep -E "^Name|^Version" || echo "  coverage NOT installed"
  pip show pytest-cov 2>/dev/null | grep -E "^Name|^Version" || echo "  pytest-cov NOT installed"
'
echo

echo "=== 2. Структура тестов apps/menu/tests/ ==="
$COMPOSE exec -T backend ls -la apps/menu/tests/ 2>/dev/null || echo "  apps/menu/tests НЕ существует"
echo

echo "=== 3. Структура тестов apps/recipes/tests/ ==="
$COMPOSE exec -T backend ls -la apps/recipes/tests/ 2>/dev/null || echo "  apps/recipes/tests НЕ существует"
echo

echo "=== 4. Все тесты по проекту ==="
$COMPOSE exec -T backend find apps/ -name "test_*.py" -not -path "*/__pycache__/*" 2>/dev/null
echo

echo "=== 5. Какие файлы в apps/menu/ — пытаемся понять что покрывать ==="
$COMPOSE exec -T backend bash -c "find apps/menu/ -maxdepth 2 -name '*.py' -not -path '*/__pycache__/*' -not -path '*/migrations/*' -not -path '*/tests/*' | sort"
echo

echo "=== 6. Какие файлы в apps/recipes/ ==="
$COMPOSE exec -T backend bash -c "find apps/recipes/ -maxdepth 2 -name '*.py' -not -path '*/__pycache__/*' -not -path '*/migrations/*' -not -path '*/tests/*' | sort" 2>/dev/null || echo "  apps/recipes отсутствует"
echo

echo "=== 7. Структура apps/ верхний уровень ==="
$COMPOSE exec -T backend ls -1 apps/ 2>/dev/null
echo

echo "=== 8. pytest.ini / pyproject coverage-конфиг ==="
$COMPOSE exec -T backend bash -c '
  echo "--- /app/pytest.ini ---"
  cat /app/pytest.ini 2>/dev/null || echo "  (нет)"
  echo
  echo "--- /app/.coveragerc ---"
  cat /app/.coveragerc 2>/dev/null || echo "  (нет)"
  echo
  echo "--- /app/pyproject.toml ---"
  cat /app/pyproject.toml 2>/dev/null || echo "  (нет)"
'
echo

echo "=== 9. Текущий список тестов в apps/menu/ с количеством ==="
$COMPOSE exec -T backend bash -c '
  for f in apps/menu/tests/test_*.py; do
    [ -f "$f" ] || continue
    n=$(grep -cE "^\s*def test_" "$f")
    echo "  $f : $n тестов"
  done
'
echo

echo "=== 10. Заголовки/docstring тестов в apps/menu/ ==="
$COMPOSE exec -T backend bash -c '
  for f in apps/menu/tests/test_*.py; do
    [ -f "$f" ] || continue
    echo "--- $f ---"
    grep -nE "^\s*def test_" "$f" | head -20
    echo
  done
'
echo

echo "=== 11. Заголовок и сигнатура generator.py ==="
$COMPOSE exec -T backend bash -c '
  echo "--- класс/функции ---"
  grep -nE "^(class |def |    def )" apps/menu/generator.py | head -40
  echo
  echo "--- кол-во строк ---"
  wc -l apps/menu/generator.py
'
echo

echo "=== 12. Прогон существующих тестов как baseline (без coverage) ==="
$COMPOSE exec -T backend pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -20 || true
echo

echo "=== 13. Попытка прогнать coverage (если установлен) ==="
$COMPOSE exec -T backend bash -c '
  if command -v coverage >/dev/null 2>&1; then
    coverage run -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -10
    echo
    echo "--- coverage report ---"
    coverage report --include="apps/menu/*,apps/recipes/*" 2>&1 | head -40
  else
    echo "  coverage не установлен — пропускаю"
  fi
' || true
echo

echo "=== 14. conftest.py ==="
$COMPOSE exec -T backend bash -c "find /app -name conftest.py -not -path '*/__pycache__/*' -not -path '*/.git/*' 2>/dev/null"
echo

echo "=== 15. Есть ли уже какой-то generator-интеграционный тест? ==="
$COMPOSE exec -T backend grep -rln "MenuGenerator\|menu-generate\|generator\.generate" apps/menu/tests/ 2>/dev/null || echo "  (нет упоминаний)"
echo

echo "=== DONE MG-601 DIAGNOSE ==="
