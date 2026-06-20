#!/usr/bin/env bash
# MenuGen: WIP-коммит локальных правок на сервере + веб-деплой (CRA -> web-dist -> nginx)
set -euo pipefail

REPO=/opt/menugen
SRC=$REPO/web/menugen-web
DIST=$REPO/web-dist
BRANCH=claude/nifty-rubin-h90pfg
PUSH=${PUSH:-1}          # 1 = запушить WIP-коммит в origin, 0 = оставить только локально
TS=$(date +%Y%m%d_%H%M%S)

cd "$REPO"

echo "==> 0. Бэкап текущего web-dist"
mkdir -p "$REPO/backups"
if [ -d "$DIST" ]; then
  tar -C "$REPO" -czf "$REPO/backups/web-dist.tar.gz.bak_${TS}" web-dist/
  echo "    $REPO/backups/web-dist.tar.gz.bak_${TS}"
fi

echo "==> 1. Ветка $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"

echo "==> 2. Промежуточный коммит локальных правок (если есть)"
COMMITTED=0
if [ -n "$(git status --porcelain)" ]; then
  git config user.name  >/dev/null 2>&1 || git config user.name  "MenuGen Server"
  git config user.email >/dev/null 2>&1 || git config user.email "server@menugen.local"
  git add -A
  git commit -m "wip(server): промежуточный коммит локальных правок перед деплоем ${TS}"
  COMMITTED=1
  echo "    закоммичено"
else
  echo "    незакоммиченных правок нет — пропуск"
fi

echo "==> 3. Подтягиваем origin/$BRANCH (rebase)"
git pull --rebase origin "$BRANCH"

if [ "$PUSH" = "1" ] && [ "$COMMITTED" = "1" ]; then
  echo "==> 3b. Пуш WIP-коммита в origin (с ретраями)"
  ok=0
  for d in 0 2 4 8 16; do
    [ "$d" -gt 0 ] && { echo "    повтор через ${d}s..."; sleep "$d"; }
    if git push -u origin "$BRANCH"; then ok=1; break; fi
  done
  [ "$ok" = "1" ] || echo "!! push не удался — код закоммичен локально, запушишь позже"
fi

echo "==> 4. Зависимости (--legacy-peer-deps обязателен)"
cd "$SRC"
npm install --legacy-peer-deps

echo "==> 5. Проверка типов + сборка (CI=false)"
npx tsc --noEmit
CI=false npm run build

echo "==> 6. build -> web-dist"
rm -rf "$DIST"; mkdir -p "$DIST"
cp -a "$SRC/build/." "$DIST/"

echo "==> 7. Reload nginx"
nginx -t && nginx -s reload

echo "==> ГОТОВО. В браузере: Ctrl+Shift+R"
echo "    nginx отдаёт:"
curl -sH 'Cache-Control: no-cache' "http://127.0.0.1:8081/?nocache=$(date +%s)" \
  | grep -oE 'src="[^"]*\.js[^"]*"' || true
