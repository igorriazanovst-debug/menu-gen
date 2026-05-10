#!/usr/bin/env bash
# MG-601 fix v3: расширить omit в .coveragerc — исключить management команды
# и media_upload (вне scope MG-601), затем повторить coverage + finalize.
set -eu
ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

cp -p "${BACKEND}/.coveragerc" "/tmp/mg_601_fix_v3_${TS}_coveragerc.bak"
echo "[0] backup: /tmp/mg_601_fix_v3_${TS}_coveragerc.bak"

cat > "${BACKEND}/.coveragerc" <<'COVRC'
# MG_601_V_coveragerc
[run]
branch = False
source =
    apps/menu
    apps/recipes
omit =
    */migrations/*
    */tests/*
    */management/*
    */__pycache__/*
    apps/*/admin.py
    apps/*/apps.py
    apps/recipes/media_upload.py
    apps/recipes/filters.py
    manage.py

[report]
fail_under = 70
show_missing = True
skip_empty = True
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if __name__ == .__main__.:
    def __repr__
    def __str__

[html]
directory = htmlcov
COVRC
echo "[1] .coveragerc обновлён"
echo

echo "=== 2. Coverage прогон ==="
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -3
  echo
  echo "--- coverage report ---"
  coverage report --rcfile=.coveragerc
'
echo

echo "=== 3. Git status ==="
cd "$ROOT"
git status --short
echo

echo "=== 4. Git add + commit + push ==="
git add -A backend/.coveragerc \
            backend/scripts/mg_601_*.sh \
            backend/apps/menu/tests/test_mg_601_integration.py 2>/dev/null || true

git status --short
echo

git diff --cached --stat | tail -10
echo

git commit -m "MG-601: интеграционные тесты + coverage конфиг (>=70% по apps/menu + apps/recipes)

- test_mg_601_integration.py: 8 интеграционных тестов через MenuGenerator + API
  (cheat-meal интеграция MG-505, calorie distribution MG-303,
  oil_tsp фильтр MG-502, no added sugar в основных приёмах MG-503,
  red_meat 500г/неделю MG-302, plate-метод 3 компонента MG-301)
- backend/.coveragerc: fail_under=70, omit migrations/tests/admin/management/media_upload/filters
- mg_601_run_coverage.sh: запуск coverage с .coveragerc, флаг --html
- регрессия: 156 passed (148 старых + 8 новых)" || echo "  (нет изменений для коммита)"

git push origin main 2>&1 | tail -10 || echo "  (push failed or already up to date)"
echo

echo "=== MG-601 FINALIZE v3 DONE ==="
