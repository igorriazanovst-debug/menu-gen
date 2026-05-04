#!/usr/bin/env bash
set -euo pipefail
cd /opt/menugen

echo "### 1. Корректная проверка (через -q + код возврата) ###"
# git check-ignore -q: exit 0 = игнорируется, exit 1 = НЕ игнорируется (включая allow), exit >1 = ошибка
set +e
git check-ignore -q MenuGen_Backlog.xlsx
RC=$?
set -e
echo "  exit code = $RC"
case "$RC" in
  0) echo "  ❌ ИГНОРИРУЕТСЯ"; exit 1;;
  1) echo "  ✅ НЕ игнорируется (или явно allowed)";;
  *) echo "  error rc=$RC"; exit 1;;
esac
echo

echo "### 2. Полное матч-объяснение (для протокола) ###"
git check-ignore -v --no-index MenuGen_Backlog.xlsx 2>&1 || true
echo

echo "### 3. Закрыть MG-204 в xlsx ###"
if [ -f /opt/menugen/backend/scripts/mg_204_close_backlog.py ]; then
  python3 /opt/menugen/backend/scripts/mg_204_close_backlog.py
else
  echo "  ⚠️ скрипт закрытия бэклога не найден — копируй mg_204_close_backlog.py из /tmp"
fi
echo

echo "### 4. git status / add / commit ###"
git add .gitignore MenuGen_Backlog.xlsx
git status --short
echo
if git diff --cached --quiet; then
  echo "  нечего коммитить (видимо .gitignore + xlsx уже зафиксированы)"
else
  git commit -m "MG-204: track MenuGen_Backlog.xlsx in git; close MG-204 (web)

- .gitignore: disable rule '/*.xlsx' that excluded MenuGen_Backlog.xlsx
- explicit !MenuGen_Backlog.xlsx allow
- MenuGen_Backlog.xlsx: mark MG-204 as ✅ (web), mobile deferred"
  echo
  echo "✅ Done. Последние 3 коммита:"
  git log --oneline -3
fi
