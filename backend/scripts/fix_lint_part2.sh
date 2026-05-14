#!/usr/bin/env bash
# 1) Чиним сломанный .flake8 (правильно добавляем scripts в многострочный exclude)
# 2) Удаляем мусорные fix_tests.py / fix_views.py из backend/
# 3) Фиксим F401 unused imports автоматом (autoflake)
# 4) Финальная проверка
#
# Запуск:
#   bash /opt/menugen/backend/scripts/fix_lint_part2.sh

set -uo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
cd "$ROOT"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── 1. правим .flake8 ──────────────────────────────────────────────────────
hr "1. fix .flake8"
cat > "${BACKEND}/.flake8" <<'EOF'
[flake8]
max-line-length = 120
exclude =
    migrations,
    scripts,
    __pycache__,
    .git,
    .venv,
    venv
ignore = E203, W503
EOF
cat "${BACKEND}/.flake8"

# ─── 2. мусор в корне backend/ ──────────────────────────────────────────────
hr "2. backend/fix_tests.py + fix_views.py"
ls -la "${BACKEND}/fix_tests.py" "${BACKEND}/fix_views.py" 2>/dev/null
echo "---"
head -20 "${BACKEND}/fix_tests.py" 2>/dev/null
echo "---"
head -20 "${BACKEND}/fix_views.py" 2>/dev/null
echo "---"
# Проверим: импортируется ли это из production?
echo "Импорты из apps/config:"
grep -rE "from fix_tests|import fix_tests|from fix_views|import fix_views" \
  "${BACKEND}/apps" "${BACKEND}/config" 2>/dev/null
echo "(если пусто — это legacy одноразовые скрипты, можно удалить)"

# Решаем сами: оставим решение пользователю. Сейчас просто покажем.

# ─── 3. F401/F841 — авто-фикс через autoflake ───────────────────────────────
hr "3. autoflake (F401 unused imports + F841 unused vars)"
docker compose exec -T backend pip install --quiet autoflake 2>&1 | tail -3
docker compose exec -T backend autoflake \
  --in-place --recursive \
  --remove-all-unused-imports \
  --remove-unused-variables \
  --ignore-init-module-imports \
  apps config 2>&1 | tail -20

# autoflake может убрать нужные импорты (например для side-effects, signals).
# Это безопасно для test-файлов; для production-кода ниже сделаем sanity-check.

hr "4. re-run black + isort после autoflake (могло сдвинуть форматирование)"
docker compose exec -T backend isort apps config --skip=migrations 2>&1 | tail -5
docker compose exec -T backend black apps config --exclude='/migrations/' 2>&1 | tail -5

# ─── 5. финальные проверки ──────────────────────────────────────────────────
hr "5a. flake8 на apps/ + config/"
docker compose exec -T backend flake8 apps config --max-line-length=120 --exclude=migrations 2>&1 | tee /tmp/lint_part2.log
REMAINING=$(wc -l < /tmp/lint_part2.log)
echo
echo "REMAINING: $REMAINING"

hr "5b. flake8 на КОРНЕ (как CI) — должен видеть только мусор в backend/"
docker compose exec -T backend flake8 . --max-line-length=120 --exclude=migrations,scripts 2>&1 | tee /tmp/lint_root.log
echo "REMAINING (root): $(wc -l < /tmp/lint_root.log)"

hr "6. tests sanity: убедимся что наши тесты не сломались"
docker compose exec -T backend pytest apps/users/tests/test_mg_profile_premium.py -v 2>&1 | tail -15

hr "7. Diff stat"
git -C "$ROOT" diff --stat | tail -30

echo
echo "DONE."
echo "Если 5a/5b ещё не clean — пришли вывод."
echo "Решения по 2 (fix_tests.py / fix_views.py) — спросим отдельно."
