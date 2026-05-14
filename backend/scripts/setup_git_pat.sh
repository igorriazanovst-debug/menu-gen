#!/usr/bin/env bash
# Настройка git-credentials через Personal Access Token (HTTPS).
#
# Требуется:
#   - GitHub PAT с правом `repo` (classic) или fine-grained на этот репо: contents:write
#   - Создать тут: https://github.com/settings/tokens
#
# Запуск:
#   bash /opt/menugen/backend/scripts/setup_git_pat.sh

set -euo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

USER_LOGIN="igorriazanovst-debug"

echo "Текущий remote:"
git remote -v
echo

# Нормализуем remote: убираем username из URL (он будет в credentials store)
CURRENT_URL="$(git remote get-url origin)"
CLEAN_URL="https://github.com/${USER_LOGIN}/menu-gen.git"
if [ "$CURRENT_URL" != "$CLEAN_URL" ]; then
  echo "Нормализую origin: $CURRENT_URL -> $CLEAN_URL"
  git remote set-url origin "$CLEAN_URL"
fi

# Запросить PAT интерактивно (без echo)
echo
echo "Создай PAT тут (если ещё нет):"
echo "  https://github.com/settings/tokens/new"
echo "  scope: repo (classic) — достаточно contents:write для fine-grained."
echo
read -r -s -p "Вставь GitHub PAT (ввод скрыт): " PAT
echo
if [ -z "${PAT:-}" ]; then
  echo "PAT пустой — выход"
  exit 1
fi

# Сохраняем в ~/.git-credentials (формат: https://USER:PAT@github.com)
CRED_FILE="${HOME}/.git-credentials"
touch "$CRED_FILE"
chmod 600 "$CRED_FILE"

# Удалим старую запись на github.com если есть
grep -v "@github.com" "$CRED_FILE" > "${CRED_FILE}.tmp" || true
mv "${CRED_FILE}.tmp" "$CRED_FILE"

echo "https://${USER_LOGIN}:${PAT}@github.com" >> "$CRED_FILE"
chmod 600 "$CRED_FILE"

# Убедимся что helper = store (он уже global=store, ставим и локально явно)
git config credential.helper store

# Очистим переменную из памяти
unset PAT

echo
echo "Проверка ls-remote:"
if git ls-remote origin HEAD >/dev/null 2>&1; then
  echo "OK: auth работает"
else
  echo "FAIL: auth не прошёл"
  exit 2
fi

echo
echo "Готово. Теперь push:"
echo "  git push origin main"
