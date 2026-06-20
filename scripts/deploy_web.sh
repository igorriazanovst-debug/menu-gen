#!/usr/bin/env bash
# MenuGen: веб-деплой ТОЛЬКО фронта (CRA -> web-dist -> nginx).
# Сборка идёт из ветки в ИЗОЛИРОВАННОМ git worktree, поэтому основное рабочее
# дерево ($REPO) — и вместе с ним backend, который раздаётся из него, — НЕ трогается.
set -euo pipefail

REPO=/opt/menugen
DIST=$REPO/web-dist
BRANCH=${BRANCH:-claude/nifty-rubin-h90pfg}   # ветку фронта можно переопределить: BRANCH=... ./deploy_web.sh
WT=/tmp/mg-web-build                          # изолированная копия ветки (worktree)
WT_SRC=$WT/web/menugen-web
TS=$(date +%Y%m%d_%H%M%S)

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

echo "==> 3. Зависимости (--legacy-peer-deps обязателен)"
cd "$WT_SRC"
npm install --legacy-peer-deps

echo "==> 4. Проверка типов + сборка (CI=false)"
npx tsc --noEmit
CI=false npm run build

echo "==> 5. build -> web-dist"
rm -rf "$DIST"; mkdir -p "$DIST"
cp -a "$WT_SRC/build/." "$DIST/"

echo "==> 6. Reload nginx"
nginx -t && nginx -s reload

echo "==> ГОТОВО. В браузере: Ctrl+Shift+R"
echo "    nginx отдаёт:"
curl -sH 'Cache-Control: no-cache' "http://127.0.0.1:8081/?nocache=$(date +%s)" \
  | grep -oE 'src="[^"]*\.js[^"]*"' || true
