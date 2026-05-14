#!/usr/bin/env bash
# DIAG: что именно ругает flake8 в нашем коммите.
#
# Запуск:
#   bash /opt/menugen/backend/scripts/diag_lint_d4315a7.sh

set -uo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. setup.cfg / .flake8 / pyproject — конфиг flake8"
ls "${ROOT}/backend/setup.cfg" "${ROOT}/backend/.flake8" "${ROOT}/backend/pyproject.toml" 2>/dev/null
echo "---"
grep -nE "\[flake8\]|max-line|extend-select|ignore" "${ROOT}/backend/setup.cfg" "${ROOT}/backend/.flake8" 2>/dev/null

hr "2. ci.yml — какие команды Backend Lint выполняет"
grep -nE "flake8|lint|black|isort" "${ROOT}/.github/workflows/ci.yml" 2>/dev/null | head -30
echo "---"
sed -n '1,120p' "${ROOT}/.github/workflows/ci.yml"

hr "3. Запуск flake8 локально через docker на нашем файле"
docker compose exec -T backend flake8 apps/users/serializers.py 2>&1 | head -30

hr "4. Запуск flake8 на всём backend/apps/users (контекст)"
docker compose exec -T backend flake8 apps/users/ 2>&1 | head -30

hr "5. Если есть black — запустить --check"
docker compose exec -T backend black --check apps/users/serializers.py 2>&1 | head -10 || echo "(black не установлен или ошибка)"

hr "6. isort --check на serializers.py"
docker compose exec -T backend isort --check-only apps/users/serializers.py 2>&1 | head -10 || echo "(isort не установлен или ошибка)"

echo
echo "=== done ==="
