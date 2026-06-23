#!/usr/bin/env bash
# Безопасно настроить nginx так, чтобы index.html НЕ кэшировался браузером
# (Cache-Control: no-store). Иначе после деплоя браузер тянет старый index.html
# со ссылкой на уже удалённый main.<hash>.js → 404 → «тёмный экран».
#
# Хэшированные ассеты (/static/...) при этом кэшируются надолго (immutable).
#
# Безопасность: бэкап конфига, вставка идемпотентна, проверка `nginx -t`,
# при ошибке — автоматический откат. Конфиг по умолчанию из MEMO; переопредели
# через CONF=/путь, если другой.
#
# Запуск (на сервере):
#   cd /opt/menugen
#   git show origin/main:scripts/nginx_no_cache_index.sh > /tmp/nginx_fix.sh
#   sed -i 's/\r$//' /tmp/nginx_fix.sh
#   bash /tmp/nginx_fix.sh
set -euo pipefail

CONF=${CONF:-/etc/nginx/sites-enabled/menugen-debug}
TS=$(date +%Y%m%d_%H%M%S)

[ -f "$CONF" ] || { echo "!! Конфиг $CONF не найден. Укажи: CONF=/path bash $0"; exit 1; }

if grep -q 'MG_NO_CACHE_INDEX' "$CONF"; then
  echo "Блок уже добавлен ранее ($CONF). Ничего не меняю."
  exit 0
fi

BAK="/tmp/$(basename "$CONF").bak_${TS}"
cp "$CONF" "$BAK"
echo "Бэкап конфига: $BAK"

# Вставляем блоки сразу после первой строки 'server {'.
# location = /index.html  -> no-store; location /static/ -> immutable.
awk '
  !done && /server[[:space:]]*\{/ {
    print
    print "    # MG_NO_CACHE_INDEX: не кэшировать index.html (иначе старый html -> 404 на новый бандл)"
    print "    location = /index.html {"
    print "        add_header Cache-Control \"no-store, must-revalidate\";"
    print "        expires off;"
    print "        try_files $uri =404;"
    print "    }"
    print "    location /static/ {"
    print "        expires 1y;"
    print "        add_header Cache-Control \"public, immutable\";"
    print "    }"
    done=1
    next
  }
  { print }
' "$CONF" > "${CONF}.new"

cp "${CONF}.new" "$CONF"
rm -f "${CONF}.new"

if nginx -t; then
  nginx -s reload
  echo "OK: index.html больше НЕ кэшируется, /static/ кэшируется надолго. nginx перезагружен."
  echo "Проверка:"
  curl -sI "http://127.0.0.1:8081/" | grep -iE 'HTTP/|cache-control' | sed 's/^/   /'
else
  echo "!! nginx -t упал — откатываю конфиг из бэкапа"
  cp "$BAK" "$CONF"
  nginx -t && nginx -s reload || true
  echo "Откат выполнен. Конфиг не изменён. Возможно, нестандартная структура —"
  echo "пришли мне 'cat $CONF', добавлю блок точечно."
  exit 1
fi
