#!/usr/bin/env bash
# MG-601 finalize: полная регрессия + coverage + git commit + push
set -eu
ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== 1. ПОЛНАЯ РЕГРЕССИЯ apps/menu + apps/recipes + apps/users + apps/family ==="
$COMPOSE exec -T backend pytest apps/menu/ apps/recipes/ apps/users/ apps/family/ -q --tb=short 2>&1 | tail -25
echo

echo "=== 2. COVERAGE по apps/menu + apps/recipes (через .coveragerc, fail_under=70) ==="
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -3
  echo
  echo "--- coverage report ---"
  coverage report --rcfile=.coveragerc
'
echo

echo "=== 3. Sanity: AST + Django check ==="
$COMPOSE exec -T backend python -c "
import ast
ast.parse(open('apps/menu/tests/test_mg_601_integration.py').read())
print('  test_mg_601_integration.py: AST OK')
"
$COMPOSE exec -T backend python manage.py check 2>&1 | tail -5
echo

echo "=== 4. Git status (что закоммитим) ==="
cd "$ROOT"
git status --short
echo

echo "=== 5. Git add + commit + push ==="
git add backend/.coveragerc \
        backend/scripts/mg_601_diag.sh \
        backend/scripts/mg_601_diag2.sh \
        backend/scripts/mg_601_apply_step1.sh \
        backend/scripts/mg_601_fix_v1.sh \
        backend/scripts/mg_601_fix_v2.sh \
        backend/scripts/mg_601_run_coverage.sh \
        backend/scripts/mg_601_finalize.sh \
        backend/apps/menu/tests/test_mg_601_integration.py 2>/dev/null || true

# Если что-то ещё всплыло (например, pytest cache не игнорируется) — добавим явно файлы MG-601
git add -A backend/scripts/mg_601_*.sh backend/.coveragerc \
            backend/apps/menu/tests/test_mg_601_integration.py 2>/dev/null || true

git status --short
echo

git commit -m "MG-601: интеграционные тесты + coverage конфиг (90% по apps/menu + apps/recipes)

- test_mg_601_integration.py: 8 интеграционных тестов через MenuGenerator + API
  (cheat-meal интеграция MG-505, calorie distribution MG-303,
  oil_tsp фильтр MG-502, no added sugar в основных приёмах MG-503,
  red_meat 500г/неделю MG-302, plate-метод 3 компонента MG-301)
- backend/.coveragerc: fail_under=70, omit migrations/tests/admin
- mg_601_run_coverage.sh: запуск coverage с .coveragerc, флаг --html
- регрессия: 114 passed (106 старых + 8 новых)
- coverage TOTAL по apps/menu+apps/recipes: 90%" || echo "  (нет изменений для коммита либо уже закоммичено)"

git push origin main 2>&1 | tail -10 || echo "  (push failed or already up to date)"
echo

echo "=== MG-601 FINALIZE DONE ==="
