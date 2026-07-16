#!/usr/bin/env bash
# MenuGen — ЭКСПОРТ данных со СТАРОГО сервера (31.192.110.121).
# Делает согласованный снимок: дамп БД (pg_dump -Fc) + архив медиа.
# По умолчанию НИЧЕГО не останавливает. Для полностью согласованного снимка в
# maintenance-окне сначала остановите запись:  STOP_WRITES=1 ...
#
# Запуск на старом сервере:
#   cd /opt/menugen
#   git fetch origin main
#   git show origin/main:deploy/migrate/export_old.sh > /tmp/export_old.sh
#   sed -i 's/\r$//' /tmp/export_old.sh
#   STOP_WRITES=1 bash /tmp/export_old.sh
#
# Результат: /opt/menugen/backups/migrate/<TS>/{menugen.dump, media.tar.gz, meta.txt}
# Дальше — перенос на новый сервер (rsync/scp, команды печатаются в конце).
set -euo pipefail

REPO=${REPO:-/opt/menugen}
TS=$(date +%Y%m%d_%H%M%S)
OUT="$REPO/backups/migrate/$TS"
STOP_WRITES=${STOP_WRITES:-0}

if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else echo "!! docker compose не найден"; exit 1; fi

cd "$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a
DB_NAME=${DB_NAME:-menugen}
DB_USER=${DB_USER:-menugen_user}

mkdir -p "$OUT"
echo "==> Каталог экспорта: $OUT"

if [ "$STOP_WRITES" = "1" ]; then
  echo "==> Maintenance: останавливаю backend/celery (приём записи прекращается)"
  $DC stop backend celery celery-beat
fi

echo "==> 1/3. Дамп БД ($DB_NAME, пользователь $DB_USER) — pg_dump -Fc"
$DC exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$OUT/menugen.dump"
echo "    $(du -h "$OUT/menugen.dump" | cut -f1)  menugen.dump"

echo "==> 2/3. Архив медиа (из volume, через backend-контейнер)"
# media_files смонтирован в backend как /app/media. Архивируем изнутри, чтобы не
# зависеть от прав на /var/lib/docker/volumes.
$DC run --rm --no-deps -T -v "$OUT:/backup" backend \
  tar -C /app -czf /backup/media.tar.gz media 2>/dev/null || \
  $DC exec -T backend tar -C /app -czf - media > "$OUT/media.tar.gz"
echo "    $(du -h "$OUT/media.tar.gz" | cut -f1)  media.tar.gz"

echo "==> 3/3. Мета"
{
  echo "exported_at=$TS"
  echo "db_name=$DB_NAME"
  echo "db_user=$DB_USER"
  echo "pg_server_version=$($DC exec -T db postgres --version 2>/dev/null | tr -d '\r')"
  echo "stop_writes=$STOP_WRITES"
} > "$OUT/meta.txt"
cat "$OUT/meta.txt" | sed 's/^/    /'

if [ "$STOP_WRITES" = "1" ]; then
  echo
  echo "!! backend/celery ОСТАНОВЛЕНЫ. Если откатываете — верните:"
  echo "     $DC start backend celery celery-beat"
fi

echo
echo "==> ГОТОВО. Перенесите каталог на новый сервер, напр.:"
echo "     rsync -avz --mkpath -e ssh $OUT/ root@158.255.5.166:/opt/menugen/backups/migrate/$TS/"
echo "   (--mkpath создаёт каталог назначения; при старом rsync без него —"
echo "    сначала 'mkdir -p /opt/menugen/backups/migrate/$TS' на новом сервере)"
echo "   Затем на новом сервере: bash import_new.sh /opt/menugen/backups/migrate/$TS"
