#!/usr/bin/env bash
set -euo pipefail
WEB="/opt/menugen/web/menugen-web"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="/opt/menugen/backups"

echo "### Бэкап текущего build ###"
if [ -d "$WEB/build" ]; then
  tar -C "$WEB" -czf "$BACKUPS/menugen-web-build.tar.gz.bak_mg204_${TS}" build/
  echo "  → $BACKUPS/menugen-web-build.tar.gz.bak_mg204_${TS}"
fi
echo

echo "### node + npm ###"
node -v
npm -v
echo

echo "### npm run build (production) ###"
cd "$WEB"
# CI=false — чтобы warnings не валили build (CRA по умолчанию падает на warnings в CI окружении)
CI=false npm run build 2>&1 | tail -60
echo
ls -la "$WEB/build/" | head -20
echo
echo "build/static/js (последние 5 файлов):"
ls -la "$WEB/build/static/js/" 2>/dev/null | tail -10
echo

echo "### nginx reload (на случай кеша) ###"
nginx -t && nginx -s reload
echo

echo "### Хеш index.html, который теперь раздаётся ###"
sleep 1
curl -s "http://31.192.110.121:8081/" -o /tmp/served_index_after.html
sha256sum /tmp/served_index_after.html
echo "  ссылки на bundle:"
grep -oE 'src="[^"]*\.js[^"]*"' /tmp/served_index_after.html | head -3
echo
echo "### Готово. В браузере: Ctrl+Shift+R (hard reload) ###"
echo
echo "Откат build:"
echo "  rm -rf $WEB/build && tar -C $WEB -xzf $BACKUPS/menugen-web-build.tar.gz.bak_mg204_${TS}"
