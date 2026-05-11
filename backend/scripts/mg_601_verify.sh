#!/usr/bin/env bash
# MG-601 git verify: что фактически в репо, и почему git add ничего не добавил
set -eu
ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
cd "$ROOT"

echo "=== 1. Последние 5 коммитов ==="
git log --oneline -5
echo

echo "=== 2. Файлы MG-601 — есть ли в индексе/HEAD ==="
for f in \
  backend/.coveragerc \
  backend/apps/menu/tests/test_mg_601_integration.py \
  backend/scripts/mg_601_apply_step1.sh \
  backend/scripts/mg_601_diag.sh \
  backend/scripts/mg_601_diag2.sh \
  backend/scripts/mg_601_finalize.sh \
  backend/scripts/mg_601_fix_v1.sh \
  backend/scripts/mg_601_fix_v2.sh \
  backend/scripts/mg_601_fix_v3.sh \
  backend/scripts/mg_601_run_coverage.sh; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "  IN-REPO: $f"
  else
    echo "  MISSING: $f"
  fi
done
echo

echo "=== 3. Список всех MG-601 коммитов ==="
git log --oneline --all -- backend/apps/menu/tests/test_mg_601_integration.py
echo

echo "=== 4. Последний коммит, затронувший .coveragerc ==="
git log -1 --oneline -- backend/.coveragerc 2>/dev/null || echo "  (нет в истории)"
echo

echo "=== 5. .gitignore — может scripts игнорится? ==="
cat .gitignore 2>/dev/null | head -30 || echo "  (нет .gitignore)"
echo

echo "=== 6. Проверка ignored scripts ==="
git check-ignore -v backend/scripts/mg_601_apply_step1.sh 2>&1 || echo "  (не игнорируется)"
git check-ignore -v backend/scripts/mg_505_backlog_inspect.sh 2>&1 || echo "  (не игнорируется)"
echo

echo "=== 7. Добавить хвосты MG-505 + MenuGen_Backlog.xlsx и закоммитить ==="
git add MenuGen_Backlog.xlsx \
        backend/scripts/mg_505_backlog_inspect.sh \
        backend/scripts/mg_505_backlog_inspect_v2.sh \
        backend/scripts/mg_505_backlog_update.sh
git status --short
echo

git commit -m "MG-505: backlog update scripts + xlsx — закрыть хвосты после MG-601" || echo "  (нечего коммитить)"
git push origin main 2>&1 | tail -5
echo

echo "=== 8. Финальный git status ==="
git status --short
git log --oneline -3
echo

echo "=== DONE ==="
