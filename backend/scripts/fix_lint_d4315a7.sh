#!/usr/bin/env bash
# Авто-фикс линта только для наших изменённых файлов (MG-profile-premium).
# Не трогает legacy-файлы (audit.py, nutrition.py — это pre-existing tech debt).
#
# Запуск:
#   bash /opt/menugen/backend/scripts/fix_lint_d4315a7.sh

set -euo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

FILE="apps/users/serializers.py"

echo "== before =="
docker compose exec -T backend flake8 "$FILE" --max-line-length=120 2>&1 | head -20 || true

echo
echo "== isort =="
docker compose exec -T backend isort "$FILE"

echo
echo "== black =="
docker compose exec -T backend black "$FILE"

echo
echo "== after flake8 =="
docker compose exec -T backend flake8 "$FILE" --max-line-length=120 2>&1 | head -20 || echo "(clean)"

echo
echo "== after isort --check =="
docker compose exec -T backend isort --check-only "$FILE" && echo "(clean)" || true

echo
echo "== after black --check =="
docker compose exec -T backend black --check "$FILE" && echo "(clean)" || true

echo
echo "DONE. Diff:"
git -C "$ROOT" diff --stat "backend/${FILE}"
