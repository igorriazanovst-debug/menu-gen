#!/usr/bin/env bash
# Принудительная ЧИСТАЯ пересборка веб-фронта из origin/main + проверка, что
# свежий код (freemium-гейт + ErrorBoundary) реально попал в бандл и отдаётся
# nginx. Сборка в изолированном worktree — основное дерево/.env не трогаем.
#
# Запуск (на сервере):
#   cd /opt/menugen
#   git fetch origin main
#   git show origin/main:scripts/redeploy_web.sh > /tmp/redeploy_web.sh
#   sed -i 's/\r$//' /tmp/redeploy_web.sh
#   bash /tmp/redeploy_web.sh
set -euo pipefail

REPO=/opt/menugen
DIST=$REPO/web-dist
BRANCH=${BRANCH:-main}
WT=/tmp/mg-web-redeploy
WT_SRC=$WT/web/menugen-web
TS=$(date +%Y%m%d_%H%M%S)
cd "$REPO"

echo "==> 1. fetch origin/$BRANCH"
git fetch origin "$BRANCH"

echo "==> 2. бэкап текущего web-dist"
mkdir -p "$REPO/backups"
[ -d "$DIST" ] && tar -C "$REPO" -czf "$REPO/backups/web-dist.bak_${TS}.tar.gz" web-dist/ && \
  echo "    backups/web-dist.bak_${TS}.tar.gz" || true

echo "==> 3. изолированный worktree из origin/$BRANCH"
git worktree remove --force "$WT" 2>/dev/null || true
rm -rf "$WT"
git worktree add --detach "$WT" "origin/$BRANCH"
cleanup() { cd "$REPO"; git worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"; }
trap cleanup EXIT

echo "==> 4. переносим .env (gitignored) в worktree"
for f in .env .env.local .env.production .env.production.local; do
  [ -f "$REPO/web/menugen-web/$f" ] && cp "$REPO/web/menugen-web/$f" "$WT_SRC/$f" && echo "    $f"
done

cd "$WT_SRC"
echo "==> 5. deps + сборка (CI=false)"
[ -d node_modules ] || npm install --legacy-peer-deps
CI=false npm run build

BUNDLE=$(ls build/static/js/main.*.js | head -1)
echo "==> 6. контроль бандла"
# Единственная блокирующая проверка: неверный API-URL.
if grep -q 'localhost:8000' "$BUNDLE"; then
  echo "    !! В бандле localhost:8000 — .env не подхватился. СТОП, web-dist не тронут."
  exit 1
fi
# Кириллица в минифицированном .js экранируется в \uXXXX, поэтому наличие фикса
# проверяем по source-map (там исходный UTF-8). Это информативно, деплой НЕ блокирует.
MAP="${BUNDLE}.map"
if [ -f "$MAP" ] && grep -q 'Что-то пошло не так' "$MAP"; then
  echo "    ErrorBoundary (свежий фикс) В сборке ✅"
else
  echo "    (ErrorBoundary по map не подтверждён — продолжаю публикацию всё равно)"
fi
if [ -f "$MAP" ] && grep -q 'Бесплатные генерации' "$MAP"; then
  echo "    Баннер квоты В сборке ✅"
fi

echo "==> 7. публикуем build -> web-dist"
rm -rf "$DIST"; mkdir -p "$DIST"
cp -a build/. "$DIST/"

echo "==> 8. reload nginx"
nginx -t && nginx -s reload || true

echo "==> 9. что сервер реально отдаёт (:8081):"
echo "    index.html ссылается на: $(grep -oE 'main\.[a-z0-9]+\.js' "$DIST/index.html" | head -1)"
echo "    nginx отдаёт хэш:        $(curl -s "http://127.0.0.1:8081/?n=$(date +%s)" | grep -oE 'main\.[a-z0-9]+\.js' | head -1)"
echo "    cache-заголовки index.html:"
curl -sI "http://127.0.0.1:8081/" | grep -iE 'HTTP/|cache-control|etag|last-modified|expires' | sed 's/^/      /'

echo
echo "==> ГОТОВО. Если хэш в браузере не совпадает с тем, что выше —"
echo "    кэшируется index.html: запусти scripts/nginx_no_cache_index.sh"
