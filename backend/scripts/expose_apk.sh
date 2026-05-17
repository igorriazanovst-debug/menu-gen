#!/usr/bin/env bash
# expose_apk.sh — выкладывает свежий APK как /apk/menugen-debug.apk на nginx :8081
set -euo pipefail

APK_DIR="/opt/menugen/_apk"
WEB_ROOT="/opt/menugen/web-dist"
APK_PUBLIC_DIR="$WEB_ROOT/apk"

echo "═══ Поиск свежего APK ═══"
LATEST=$(find "$APK_DIR" -name '*.apk' -type f -printf '%T@ %p\n' | sort -rn | head -1 | cut -d' ' -f2-)
if [ -z "$LATEST" ]; then
  echo "ERROR: APK не найден в $APK_DIR"
  exit 1
fi
echo "  Найден: $LATEST"
ls -lh "$LATEST"

echo
echo "═══ Копирование в web-dist/apk/ ═══"
mkdir -p "$APK_PUBLIC_DIR"
cp -f "$LATEST" "$APK_PUBLIC_DIR/menugen-debug.apk"
# Также сохраним именованный
BASENAME=$(basename "$LATEST")
cp -f "$LATEST" "$APK_PUBLIC_DIR/$BASENAME"
ls -lh "$APK_PUBLIC_DIR/"

echo
echo "═══ Проверка nginx-конфига menugen-debug ═══"
NGINX_CONF="/etc/nginx/sites-available/menugen-debug"
if ! grep -q 'location /apk/' "$NGINX_CONF"; then
  echo "  Добавляю location /apk/ в $NGINX_CONF"
  # Вставим перед закрывающей фигурной скобкой сервера
  python3 <<PY
import re
p = "$NGINX_CONF"
src = open(p).read()
block = """
    location /apk/ {
        alias /opt/menugen/web-dist/apk/;
        autoindex on;
        default_type application/vnd.android.package-archive;
        add_header Content-Disposition 'attachment';
    }
"""
# Вставка перед последней '}'
idx = src.rfind('}')
new = src[:idx] + block + src[idx:]
open(p, 'w').write(new)
print("  → patched")
PY
else
  echo "  location /apk/ уже есть"
fi

echo
echo "═══ Reload nginx ═══"
nginx -t
systemctl reload nginx
echo "  → reloaded"

echo
echo "═══ Проверка доступа ═══"
curl -sS -m 5 -o /dev/null -w "  /apk/ index → HTTP %{http_code}\n" http://127.0.0.1:8081/apk/
curl -sS -m 5 -o /dev/null -w "  /apk/menugen-debug.apk → HTTP %{http_code}\n" http://127.0.0.1:8081/apk/menugen-debug.apk
curl -sS -m 5 -o /dev/null -w "  EXT /apk/menugen-debug.apk → HTTP %{http_code}\n" http://31.192.110.121:8081/apk/menugen-debug.apk

echo
echo "═══ DONE ═══"
echo "Качай на телефон с URL:"
echo "  http://31.192.110.121:8081/apk/menugen-debug.apk"
echo "Список доступных версий:"
echo "  http://31.192.110.121:8081/apk/"
