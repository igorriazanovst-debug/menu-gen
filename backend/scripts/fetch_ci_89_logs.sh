#!/usr/bin/env bash
# Скачать логи последнего failed CI-run на main и показать ключевые ошибки.
#
# Запуск:
#   bash /opt/menugen/backend/scripts/fetch_ci_89_logs.sh

set -uo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

REPO="$(git remote get-url origin | sed -E 's|.*[:/]([^/]+/[^/.]+)(\.git)?$|\1|')"
SHA="$(git rev-parse HEAD)"

if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  echo "gh CLI отсутствует или не авторизован. Открой в браузере:"
  echo "  https://github.com/${REPO}/actions"
  echo "Кликни на failed run, скопируй красные шаги — пришли сюда."
  exit 0
fi

echo "Последние 5 runs на main:"
gh run list --repo "$REPO" --branch main --limit 5

echo
echo "Ищу failed run для $SHA..."
RUN_ID="$(gh run list --repo "$REPO" --branch main --limit 10 \
  --json databaseId,headSha,conclusion,name \
  --jq '.[] | select(.headSha=="'"$SHA"'") | select(.conclusion=="failure") | .databaseId' \
  | head -1)"

if [ -z "$RUN_ID" ]; then
  echo "Не нашёл failed run для $SHA. Беру последний failed на main:"
  RUN_ID="$(gh run list --repo "$REPO" --branch main --limit 10 \
    --json databaseId,conclusion,name \
    --jq '.[] | select(.conclusion=="failure") | .databaseId' | head -1)"
fi

echo "Run id: $RUN_ID"
echo
echo "==== failed steps ===="
gh run view "$RUN_ID" --repo "$REPO" --log-failed 2>&1 | tail -150
