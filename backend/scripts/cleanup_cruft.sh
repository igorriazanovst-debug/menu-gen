#!/usr/bin/env bash
# MG-profile-premium cleanup:
#   1) удалить из git track:
#      - корневой apply_mg_profile_premium.sh (мусор)
#      - mobile/menugen_app/.bak-*/ (backup-папки от Drift fix)
#      - все одноразовые скрипты в backend/scripts/ (diag_*, fix_*, apply_*,
#        commit_*, install_*, fetch_*, list_*, setup_*, wait_*, pin_*)
#   2) обновить .gitignore чтобы это больше не лезло
#   3) показать diff и попросить пользователя закоммитить
#
# Локально файлы в backend/scripts/ ОСТАЮТСЯ — мы их только убираем из git track.
#
# Запуск:
#   bash /opt/menugen/backend/scripts/cleanup_cruft.sh

set -uo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── 1. .gitignore ──────────────────────────────────────────────────────────
hr "1. .gitignore patches"
GI="${ROOT}/.gitignore"
touch "$GI"

# Идемпотентно: каждое правило добавляем только если его нет.
add_rule() {
  local rule="$1"
  if grep -qxF "$rule" "$GI"; then
    echo "  already: $rule"
  else
    echo "$rule" >> "$GI"
    echo "  added:   $rule"
  fi
}

# Заголовок секции
if ! grep -q "# MG-cleanup" "$GI"; then
  echo "" >> "$GI"
  echo "# MG-cleanup: one-off scripts and backup dirs, not tracked" >> "$GI"
fi

add_rule "/apply_*.sh"
add_rule "/backend/scripts/diag_*.sh"
add_rule "/backend/scripts/diag_*.py"
add_rule "/backend/scripts/fix_*.sh"
add_rule "/backend/scripts/fix_*.py"
add_rule "/backend/scripts/apply_*.sh"
add_rule "/backend/scripts/commit_*.sh"
add_rule "/backend/scripts/install_*.sh"
add_rule "/backend/scripts/fetch_*.sh"
add_rule "/backend/scripts/list_*.sh"
add_rule "/backend/scripts/setup_*.sh"
add_rule "/backend/scripts/wait_*.sh"
add_rule "/backend/scripts/pin_*.sh"
add_rule "/backend/scripts/edit_*.py"
add_rule "/mobile/menugen_app/.bak-*/"

echo
echo "Финальный .gitignore (последние 30 строк):"
tail -30 "$GI"

# ─── 2. git rm --cached (untrack без удаления локального файла) ────────────
hr "2. untrack tracked cruft"

untrack() {
  local pat="$1"
  # ищем tracked файлы под паттерн
  local files
  files=$(git -C "$ROOT" ls-files "$pat" 2>/dev/null)
  if [ -z "$files" ]; then
    echo "  nothing to untrack for: $pat"
    return
  fi
  echo "$files" | while read -r f; do
    [ -z "$f" ] && continue
    git -C "$ROOT" rm --cached -r --quiet -- "$f" 2>/dev/null && echo "  untracked: $f"
  done
}

untrack "apply_*.sh"
untrack "backend/scripts/diag_*.sh"
untrack "backend/scripts/diag_*.py"
untrack "backend/scripts/fix_*.sh"
untrack "backend/scripts/fix_*.py"
untrack "backend/scripts/apply_*.sh"
untrack "backend/scripts/commit_*.sh"
untrack "backend/scripts/install_*.sh"
untrack "backend/scripts/fetch_*.sh"
untrack "backend/scripts/list_*.sh"
untrack "backend/scripts/setup_*.sh"
untrack "backend/scripts/wait_*.sh"
untrack "backend/scripts/pin_*.sh"
untrack "backend/scripts/edit_*.py"
untrack "mobile/menugen_app/.bak-20260513-170735"
untrack "mobile/menugen_app/.bak-20260513-184525"

# ─── 3. итог ────────────────────────────────────────────────────────────────
hr "3. summary"
echo "git status:"
git -C "$ROOT" status --short | head -50
echo
echo "diff stat:"
git -C "$ROOT" diff --cached --stat | tail -20

echo
echo "DONE. Если всё ок — закоммить:"
echo "  cd ${ROOT}"
echo "  git add .gitignore"
echo "  git commit -m 'chore(repo): untrack one-off scripts and .bak dirs; add .gitignore rules'"
echo "  git push origin main"
