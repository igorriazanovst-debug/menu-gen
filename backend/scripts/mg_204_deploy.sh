#!/usr/bin/env bash
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
DIST="/opt/menugen/web-dist"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="/opt/menugen/backups"

echo "### Бэкап текущего web-dist ###"
if [ -d "$DIST" ]; then
  tar -C "$(dirname "$DIST")" -czf "$BACKUPS/web-dist.tar.gz.bak_mg204_${TS}" "$(basename "$DIST")"
  echo "  → $BACKUPS/web-dist.tar.gz.bak_mg204_${TS}"
fi
echo

echo "### Что было в web-dist (старое) ###"
ls -la "$DIST/" | head -10
echo "  bundle ссылка (старая):"
grep -oE 'src="[^"]*\.js[^"]*"' "$DIST/index.html" 2>/dev/null | head -1
echo

echo "### Чистим web-dist и копируем новый build ###"
rm -rf "$DIST"
mkdir -p "$DIST"
cp -a "$WEB/build/." "$DIST/"
echo
echo "### Что теперь в web-dist ###"
ls -la "$DIST/" | head -10
echo "  bundle ссылка (новая):"
grep -oE 'src="[^"]*\.js[^"]*"' "$DIST/index.html" | head -1
echo
echo "  список static/js:"
ls -la "$DIST/static/js/" | head -10
echo

echo "### nginx reload ###"
nginx -t && nginx -s reload
echo

echo "### Проверка по http (с no-cache) ###"
sleep 1
curl -sH 'Cache-Control: no-cache' -o /tmp/served_after_deploy.html "http://31.192.110.121:8081/?nocache=$(date +%s)"
echo "  отдаваемый bundle:"
grep -oE 'src="[^"]*\.js[^"]*"' /tmp/served_after_deploy.html | head -1
echo "  sha256 served vs build:"
echo "  served: $(sha256sum /tmp/served_after_deploy.html | awk '{print $1}')"
echo "  build:  $(sha256sum $WEB/build/index.html | awk '{print $1}')"
echo
echo "### Готово. В браузере: Ctrl+Shift+R ###"
echo
echo "Откат: rm -rf $DIST && tar -C $(dirname $DIST) -xzf $BACKUPS/web-dist.tar.gz.bak_mg204_${TS}"
