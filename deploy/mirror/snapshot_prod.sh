#!/usr/bin/env bash
# MG_DEVMIRROR — снимок ПРОДА для переноса на dev. Запускать НА ПРОДЕ.
#
# Ничего не останавливает и ничего не меняет: только читает. Прод во время
# снимка продолжает работать; согласованность обеспечивает сам pg_dump (он
# видит одно состояние базы на момент старта).
#
#   cd /opt/menugen
#   bash deploy/mirror/snapshot_prod.sh
#
# Результат: /opt/menugen/backups/mirror/<TS>/{menugen.dump, media.tar.gz, meta.txt}
# Дальше — команда переноса на dev печатается в конце.
set -euo pipefail

REPO=${REPO:-/opt/menugen}
TS=$(date +%Y%m%d_%H%M%S)
OUT="$REPO/backups/mirror/$TS"
WITH_MEDIA=${WITH_MEDIA:-1}

if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else echo "!! docker compose не найден"; exit 1; fi

cd "$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a
DB_NAME=${DB_NAME:-menugen}
DB_USER=${DB_USER:-menugen_user}

mkdir -p "$OUT"
echo "==> Снимок прода в $OUT"

echo "==> 1/3. Дамп БД ($DB_NAME) — pg_dump -Fc"
$DC exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$OUT/menugen.dump"
echo "    $(du -h "$OUT/menugen.dump" | cut -f1)  menugen.dump"

if [ "$WITH_MEDIA" = "1" ]; then
  echo "==> 2/3. Архив медиа (полтора гигабайта — это надолго; WITH_MEDIA=0 пропустит)"
  $DC exec -T backend tar -C /app -czf - media > "$OUT/media.tar.gz"
  echo "    $(du -h "$OUT/media.tar.gz" | cut -f1)  media.tar.gz"
else
  echo "==> 2/3. Медиа пропущены (WITH_MEDIA=0)"
fi

echo "==> 3/3. Мета"
{
  echo "snapshot_at=$TS"
  echo "source=prod"
  echo "db_name=$DB_NAME"
  echo "git_commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "git_branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  echo "with_media=$WITH_MEDIA"
} > "$OUT/meta.txt"
sed 's/^/    /' "$OUT/meta.txt"

echo
echo "==> ГОТОВО. Перенести на dev:"
echo "     rsync -avz -e ssh $OUT/ root@31.192.110.121:/opt/menugen/backups/mirror/$TS/"
echo "   Затем НА DEV:"
echo "     cd /opt/menugen && bash deploy/mirror/restore_dev.sh /opt/menugen/backups/mirror/$TS"
