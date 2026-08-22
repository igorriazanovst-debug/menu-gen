#!/usr/bin/env bash
# MenuGen: веб-деплой ТОЛЬКО фронта (CRA -> web-dist -> nginx).
# Сборка идёт из ветки в ИЗОЛИРОВАННОМ git worktree, поэтому основное рабочее
# дерево ($REPO) — и вместе с ним backend, который раздаётся из него, — НЕ трогается.
set -euo pipefail

REPO=/opt/menugen
DIST=$REPO/web-dist
# Ветка по умолчанию — main.
#
# Раньше здесь стояла фичеветка той сессии, в которой скрипт писался. Забытая
# переменная окружения (`BRANCH=main ...` отдельной строкой — это присваивание,
# а не запуск с переменной) означала не отказ, а молчаливый откат прода на код
# полугодовой давности: шаг синхронизации кода идёт ДО вопроса о миграциях, и
# runserver подхватывает файлы сам. Дефолт должен быть безопасным.
BRANCH=${BRANCH:-main}
WT=/tmp/mg-web-build                          # изолированная копия ветки (worktree)
WT_SRC=$WT/web/menugen-web
TS=$(date +%Y%m%d_%H%M%S)
# URL для финальной проверки, что nginx отдаёт свежий бандл. dev/старый: :8081.
# Прод (menugen.ru): nginx на 80 — переопредели WEB_URL=http://127.0.0.1 ...
WEB_URL=${WEB_URL:-http://127.0.0.1:8081}

cd "$REPO"
MAINBR=$(git rev-parse --abbrev-ref HEAD)
echo "==> Основное дерево остаётся на ветке: $MAINBR (backend не трогаем)"

echo "==> 0. Бэкап текущего web-dist"
mkdir -p "$REPO/backups"
if [ -d "$DIST" ]; then
  tar -C "$REPO" -czf "$REPO/backups/web-dist.tar.gz.bak_${TS}" web-dist/
  echo "    $REPO/backups/web-dist.tar.gz.bak_${TS}"
fi

echo "==> 1. Фетч ветки фронта: $BRANCH"
git fetch origin "$BRANCH"

echo "==> 2. Изолированный worktree из origin/$BRANCH"
# на случай, если предыдущий запуск не подчистил за собой
git worktree remove --force "$WT" 2>/dev/null || true
rm -rf "$WT"
git worktree add --detach "$WT" "origin/$BRANCH"

cleanup() {
  echo "==> Чистка worktree"
  cd "$REPO"
  git worktree remove --force "$WT" 2>/dev/null || true
  rm -rf "$WT"
}
trap cleanup EXIT

echo "==> 2b. Переносим локальный .env (gitignored) в worktree"
# .env c REACT_APP_API_BASE_URL лежит в основном дереве и в .gitignore,
# поэтому в чистый checkout ветки он не попадает. Без него CRA соберётся
# с дефолтным http://localhost:8000/api/v1 и логин сломается.
ENV_FOUND=0
for f in .env .env.local .env.production .env.production.local; do
  if [ -f "$REPO/web/menugen-web/$f" ]; then
    cp "$REPO/web/menugen-web/$f" "$WT_SRC/$f"
    echo "    скопирован $f"
    ENV_FOUND=1
  fi
done
if [ "$ENV_FOUND" = "0" ]; then
  echo "!! ВНИМАНИЕ: .env не найден в $REPO/web/menugen-web — сборка пойдёт с дефолтным"
  echo "!! API-URL (localhost:8000) и логин сломается. Создай .env с REACT_APP_API_BASE_URL."
fi

echo "==> 3. Зависимости (--legacy-peer-deps обязателен)"
cd "$WT_SRC"
npm install --legacy-peer-deps

echo "==> 4. Проверка типов + сборка (CI=false)"
npx tsc --noEmit
CI=false npm run build

echo "==> 4b. Контроль API-URL в собранном бандле"
BUNDLE=$(ls "$WT_SRC"/build/static/js/main.*.js | head -1)
if grep -q 'localhost:8000' "$BUNDLE"; then
  echo "!! В бандле остался localhost:8000 — .env не подхватился. Деплой остановлен,"
  echo "!! web-dist НЕ тронут (вход не сломается). Проверь $REPO/web/menugen-web/.env"
  exit 1
fi
echo "    OK, baked API-URL:"
grep -oE 'https?://[a-zA-Z0-9_.:-]+/api/v[0-9]+|/api/v[0-9]+' "$BUNDLE" | sort -u | sed 's/^/      /'

echo "==> 5. build -> web-dist"
rm -rf "$DIST"; mkdir -p "$DIST"
cp -a "$WT_SRC/build/." "$DIST/"

echo "==> 6. Reload nginx"
nginx -t && nginx -s reload

echo "==> ГОТОВО. В браузере: Ctrl+Shift+R"
echo "    nginx отдаёт:"
curl -sH 'Cache-Control: no-cache' "$WEB_URL/?nocache=$(date +%s)" \
  | grep -oE 'src="[^"]*\.js[^"]*"' || true
