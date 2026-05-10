#!/usr/bin/env bash
# Уборка мусорных файлов из репо menugen.
# - удаляет случайные файлы (=, grain, protein)
# - удаляет .bak_* файлы
# - расширяет .gitignore
set -uo pipefail

REPO="/opt/menugen"
cd "$REPO" || { echo "❌ нет $REPO"; exit 1; }

echo "=== git status ДО уборки ==="
git status -s
echo

# ── 1. удаляем случайные файлы (= grain protein) ───────────────────────────
echo "=== [1/4] удаление случайных файлов в корне репо ==="
for f in "=" "grain" "protein"; do
  if [ -e "$REPO/$f" ]; then
    echo "  - $REPO/$f ($(file "$REPO/$f" | cut -d: -f2))"
    rm -f "$REPO/$f"
  fi
done
echo

# ── 2. удаляем .bak_mg* файлы из дерева репо ───────────────────────────────
echo "=== [2/4] удаление .bak_mg* файлов из репо ==="
find "$REPO/backend" "$REPO/web" "$REPO/mobile" -type f -name "*.bak_mg*" 2>/dev/null \
  | while read -r f; do
      echo "  - $f"
      rm -f "$f"
    done
echo

# ── 3. расширяем .gitignore ────────────────────────────────────────────────
echo "=== [3/4] расширение .gitignore ==="
GITIGNORE="$REPO/.gitignore"
[ -f "$GITIGNORE" ] || touch "$GITIGNORE"

MARK="# MG_cleanup_V_gitignore"
if grep -q "$MARK" "$GITIGNORE"; then
  echo "  уже расширен — skip"
else
  cat >> "$GITIGNORE" <<EOF

$MARK
*.bak
*.bak_*
*.bak_mg*
.bak_mg*
/tmp/mg_*
backend/apps/*/migrations/*.bak*
EOF
  echo "  ✅ обновлён"
fi
echo

# ── 4. коммит ──────────────────────────────────────────────────────────────
echo "=== [4/4] git add + commit ==="
git add -A "$GITIGNORE"
git add -u  # учтёт удаления, в том числе уже отслеживаемых .bak

git status -s
echo

read -rp "Закоммитить уборку? [y/N]: " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
  git commit -m "chore: уборка мусорных файлов и расширение .gitignore

- удалены случайные файлы в корне (=, grain, protein) от опечаток в shell-командах
- удалены .bak_mg* файлы (бэкапы должны жить в /tmp/, не в репо)
- .gitignore: добавлены правила для *.bak, .bak_mg*, /tmp/mg_*"
  echo
  echo "git log -1:"
  git log --oneline -1
  echo
  echo "Для push:"
  echo "  git push"
else
  echo "отмена коммита"
fi
