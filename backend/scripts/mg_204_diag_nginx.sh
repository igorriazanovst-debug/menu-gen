#!/usr/bin/env bash
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"

echo "### A. Что лежит в build/index.html ###"
echo "  путь: $WEB/build/index.html"
echo "  mtime: $(stat -c '%y' $WEB/build/index.html)"
echo "  sha256: $(sha256sum $WEB/build/index.html | awk '{print $1}')"
echo "  bundle ссылка:"
grep -oE 'src="[^"]*\.js[^"]*"' "$WEB/build/index.html" | head -3
echo
echo "  список build/static/js/:"
ls -la "$WEB/build/static/js/" 2>/dev/null
echo

echo "### B. Что отдаёт nginx по http://31.192.110.121:8081/ (с Cache-Control: no-cache) ###"
curl -sH 'Cache-Control: no-cache' -o /tmp/served_now.html -D /tmp/served_now.headers "http://31.192.110.121:8081/?nocache=$(date +%s)"
echo "  --- response headers ---"
cat /tmp/served_now.headers
echo
echo "  sha256: $(sha256sum /tmp/served_now.html | awk '{print $1}')"
echo "  bundle ссылка:"
grep -oE 'src="[^"]*\.js[^"]*"' /tmp/served_now.html | head -3
echo

echo "### C. Сравнение sha256 ###"
A=$(sha256sum "$WEB/build/index.html" | awk '{print $1}')
B=$(sha256sum /tmp/served_now.html | awk '{print $1}')
if [ "$A" = "$B" ]; then
  echo "  MATCH ✅ — nginx отдаёт тот же index.html, значит проблема была в браузерном кеше"
else
  echo "  MISMATCH ❌ — nginx отдаёт ДРУГОЙ index.html, не тот, что в build/"
fi
echo

echo "### D. nginx конфиг: что является root для /family / /menu / /family/ ###"
echo "--- Где упоминается menugen-web в nginx ---"
grep -rnE "menugen|/opt/menugen|root |alias |try_files" /etc/nginx/ 2>/dev/null | grep -v "#" | head -50
echo
echo "--- Конкретно server-блок для 8081 ---"
for f in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf; do
  [ -f "$f" ] || continue
  if grep -q "8081" "$f"; then
    echo "===== $f ====="
    cat "$f"
    echo
  fi
done
echo

echo "### E. Проверим есть ли симлинк build → куда-то ###"
ls -la "$WEB/build" | head -5
file "$WEB/build" 2>/dev/null || true
echo

echo "### F. Запросим сам bundle (то, что отдаёт nginx) ###"
BUNDLE_URL=$(grep -oE '/static/js/main\.[a-z0-9]+\.js' /tmp/served_now.html | head -1)
if [ -n "$BUNDLE_URL" ]; then
  echo "  bundle url из served index.html: $BUNDLE_URL"
  curl -sI "http://31.192.110.121:8081${BUNDLE_URL}?nocache=$(date +%s)" | head -10
fi
