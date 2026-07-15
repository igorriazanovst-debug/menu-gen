#!/usr/bin/env bash
# MenuGen — сбор фактов о СТАРОМ сервере перед переносом. ТОЛЬКО ЧТЕНИЕ.
# Ничего не меняет, не останавливает и не удаляет. Печатает то, что нужно, чтобы
# финализировать скрипты bootstrap/export/import для нового сервера.
#
# Запуск на старом сервере (31.192.110.121):
#   cd /opt/menugen
#   git fetch origin main
#   git show origin/main:deploy/migrate/collect_facts.sh > /tmp/collect_facts.sh
#   sed -i 's/\r$//' /tmp/collect_facts.sh
#   bash /tmp/collect_facts.sh 2>&1 | tee /tmp/menugen_facts.txt
#   # затем пришлите содержимое /tmp/menugen_facts.txt
set -uo pipefail

REPO=${REPO:-/opt/menugen}
line() { printf '\n===== %s =====\n' "$1"; }

# docker compose v2/v1
if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else DC=""; fi

line "ДАТА / ХОСТ"
date; hostname; uname -a

line "OS"
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION)=' || true

line "REPO PATH / GIT"
cd "$REPO" 2>/dev/null && {
  pwd
  echo "ветка: $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  echo "HEAD:  $(git rev-parse --short HEAD 2>/dev/null)"
} || echo "!! $REPO не найден"

line "DOCKER COMPOSE — сервисы и статусы"
echo "compose cmd: ${DC:-НЕ НАЙДЕН}"
[ -n "$DC" ] && (cd "$REPO" && $DC ps) || true

line "DOCKER — версии образов"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true

line "DOCKER VOLUMES"
docker volume ls 2>/dev/null | grep -i menugen || docker volume ls 2>/dev/null || true

line ".env — КЛЮЧИ (значения скрыты, кроме несекретных)"
# Печатаем только имена ключей + значения безопасных (не секретных) переменных,
# чтобы не светить пароли/токены в выводе.
if [ -f "$REPO/.env" ]; then
  while IFS= read -r kv; do
    case "$kv" in ''|\#*) continue;; esac
    k=${kv%%=*}
    case "$k" in
      SECRET_KEY|DB_PASSWORD|*API_KEY|EMAIL_HOST_PASSWORD|*_TOKEN|*_SECRET)
        echo "$k=***(скрыто)";;
      *)
        echo "$kv";;
    esac
  done < "$REPO/.env"
else
  echo "!! $REPO/.env не найден"
fi

line "POSTGRES — версия сервера"
[ -n "$DC" ] && (cd "$REPO" && $DC exec -T db psql -U "${DB_USER:-menugen}" -d "${DB_NAME:-menugen}" -c 'SHOW server_version;' 2>/dev/null) || true
[ -n "$DC" ] && (cd "$REPO" && $DC exec -T db postgres --version 2>/dev/null) || true

line "POSTGRES — размер БД и топ-таблиц"
[ -n "$DC" ] && (cd "$REPO" && $DC exec -T db psql -U "${DB_USER:-menugen}" -d "${DB_NAME:-menugen}" -c \
  "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;" 2>/dev/null) || true
[ -n "$DC" ] && (cd "$REPO" && $DC exec -T db psql -U "${DB_USER:-menugen}" -d "${DB_NAME:-menugen}" -c \
  "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) AS size FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 15;" 2>/dev/null) || true

line "MEDIA — размер и число файлов"
# volume media_files смонтирован в backend как /app/media
[ -n "$DC" ] && (cd "$REPO" && $DC exec -T backend sh -c 'du -sh /app/media 2>/dev/null; find /app/media -type f | wc -l' 2>/dev/null) || true
# путь volume на хосте
docker volume inspect menugen_media_files 2>/dev/null | grep -i Mountpoint || \
  docker volume inspect "$(docker volume ls -q | grep -i media | head -1)" 2>/dev/null | grep -i Mountpoint || true

line "NGINX — конфиг (полный дамп)"
nginx -T 2>/dev/null || echo "!! nginx -T недоступен (нет прав/не установлен на хосте)"

line "NGINX — какие порты слушает"
ss -ltnp 2>/dev/null | grep -E ':(80|443|8081|8003|8000)\b' || netstat -ltnp 2>/dev/null | grep -E ':(80|443|8081|8003|8000)\b' || true

line "TLS / СЕРТИФИКАТЫ"
certbot certificates 2>/dev/null || echo "certbot не установлен / нет сертификатов"
ls -la /etc/letsencrypt/live 2>/dev/null || true

line "CRON / systemd таймеры (бэкапы, продление cert)"
crontab -l 2>/dev/null || echo "(root crontab пуст)"
systemctl list-timers 2>/dev/null | grep -iE 'certbot|backup|menugen' || true

line "DNS / ВНЕШНИЙ IP"
curl -s https://api.ipify.org 2>/dev/null || true; echo

line "VK OAuth / платёжные callback-URL в .env (имена ключей)"
grep -iE 'VK|OAUTH|REDIRECT|CALLBACK|WEBHOOK|PAYMENT|YOOKASSA|CLOUDPAYMENTS' "$REPO/.env" 2>/dev/null \
  | sed -E 's/=(.*)/=<...>/' || echo "(в .env нет таких ключей — проверьте настройки в БД/админке)"

line "ГОТОВО"
echo "Пришлите вывод целиком (файл /tmp/menugen_facts.txt)."
