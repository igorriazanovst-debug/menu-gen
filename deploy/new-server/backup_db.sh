#!/usr/bin/env bash
# MenuGen — ночной бэкап БД на НОВОМ сервере. pg_dump -Fc + ротация.
# Ставится в cron root'а (пример ниже). Дампы кладём в /opt/menugen/backups/db.
#
# Установка cron (ежедневно в 03:30):
#   ( crontab -l 2>/dev/null; echo '30 3 * * * /opt/menugen/deploy/new-server/backup_db.sh >> /var/log/menugen-backup.log 2>&1' ) | crontab -
#
# Ручной прогон:
#   bash /opt/menugen/deploy/new-server/backup_db.sh
set -euo pipefail

REPO=${REPO:-/opt/menugen}
OUT="$REPO/backups/db"
KEEP=${KEEP:-14}                 # сколько последних дампов хранить
TS=$(date +%Y%m%d_%H%M%S)

if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else echo "!! docker compose не найден"; exit 1; fi

cd "$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a
DB_NAME=${DB_NAME:-menugen}
DB_USER=${DB_USER:-menugen_user}

mkdir -p "$OUT"
FILE="$OUT/menugen_${TS}.dump"

$DC exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$FILE"
echo "$(date '+%F %T')  бэкап: $FILE ($(du -h "$FILE" | cut -f1))"

# Ротация: оставляем последние $KEEP файлов.
ls -1t "$OUT"/menugen_*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old" && echo "  удалён старый: $old"
done
