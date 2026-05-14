#!/usr/bin/env bash
# DIAG: оценка масштаба tech debt в backend/scripts + что делать.
ROOT="${PROJECT_DIR:-/opt/menugen}"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. backend/scripts/ — что это вообще"
ls "${ROOT}/backend/scripts/" 2>/dev/null | head -50
echo "---"
echo "Total .py files in backend/scripts/:"
find "${ROOT}/backend/scripts" -maxdepth 1 -name "*.py" 2>/dev/null | wc -l

hr "2. Импортируются ли эти скрипты из production-кода?"
for f in "${ROOT}/backend/scripts/"*.py; do
  name="$(basename "$f" .py)"
  hits=$(grep -rE "from scripts.${name}|import scripts.${name}" "${ROOT}/backend/apps" "${ROOT}/backend/config" 2>/dev/null | wc -l)
  if [ "$hits" -gt 0 ]; then
    echo "USED: $name ($hits hits)"
  fi
done
echo "(если пусто — ни один скрипт не импортируется из apps/config)"

hr "3. flake8 на ./apps + ./config (production-код только)"
docker compose -f "${ROOT}/docker-compose.yml" exec -T backend \
  flake8 apps config --max-line-length=120 --exclude=migrations 2>&1 | tail -30 || true

hr "4. black --check на ./apps + ./config"
docker compose -f "${ROOT}/docker-compose.yml" exec -T backend \
  black --check apps config --exclude=migrations 2>&1 | tail -20 || true

hr "5. isort --check на ./apps + ./config"
docker compose -f "${ROOT}/docker-compose.yml" exec -T backend \
  isort --check-only apps config --skip=migrations 2>&1 | tail -20 || true

hr "6. Текущая ci.yml — Backend Lint job ПОЛНОСТЬЮ"
sed -n '1,40p' "${ROOT}/.github/workflows/ci.yml"

hr "7. README/CONTRIBUTING — есть ли упоминание про backend/scripts/?"
grep -lE "backend/scripts|one-off|data ops|ad-hoc" \
  "${ROOT}/README.md" "${ROOT}/CONTRIBUTING.md" \
  "${ROOT}/backend/README.md" "${ROOT}/backend/scripts/README"* 2>/dev/null | head -5

echo
echo "=== done ==="
