#!/usr/bin/env bash
# MenuGen — ИМПОРТ данных на НОВЫЙ сервер (158.255.5.166 / menugen.ru).
# Восстанавливает дамп БД и медиа в уже поднятую инфраструктуру (Фаза B).
# Идемпотентно: pg_restore --clean --if-exists перезальёт схему+данные.
#
# Предусловия: выполнен bootstrap_new.sh (docker up, .env готов, БД мигрирована).
#
# Запуск на новом сервере:
#   cd /opt/menugen
#   bash deploy/migrate/import_new.sh /opt/menugen/backups/migrate/<TS>
set -euo pipefail

REPO=${REPO:-/opt/menugen}
SRC=${1:-}
if [ -z "$SRC" ] || [ ! -f "$SRC/menugen.dump" ]; then
  echo "!! Использование: bash import_new.sh <каталог с menugen.dump и media.tar.gz>"
  exit 1
fi

if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else echo "!! docker compose не найден"; exit 1; fi

cd "$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a
DB_NAME=${DB_NAME:-menugen}
DB_USER=${DB_USER:-menugen_user}

echo "==> Источник: $SRC"
[ -f "$SRC/meta.txt" ] && sed 's/^/    /' "$SRC/meta.txt"

echo "==> 1/5. Останавливаю backend/celery (на время восстановления)"
$DC stop backend celery celery-beat 2>/dev/null || true
$DC up -d db redis
echo "    жду готовности БД…"
for _ in $(seq 1 30); do
  if $DC exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then break; fi
  sleep 2
done

echo "==> 2/5. Восстановление БД (pg_restore --clean --if-exists)"
# --clean удаляет объекты перед пересозданием; --if-exists глушит ошибки отсутствия.
$DC exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner \
  < "$SRC/menugen.dump" 2>&1 | grep -vE 'does not exist, skipping' | sed 's/^/    /' || true

echo "==> 3/5. Восстановление медиа в volume"
if [ -f "$SRC/media.tar.gz" ]; then
  # Распаковываем внутрь контейнера в /app (media_files смонтирован в /app/media).
  $DC up -d backend
  sleep 3
  # /app/media — точка монтирования volume: удаляем СОДЕРЖИМОЕ, не саму папку.
  $DC exec -T backend sh -c 'find /app/media -mindepth 1 -delete 2>/dev/null; mkdir -p /app/media' || true
  $DC exec -T backend tar -C /app -xzf - < "$SRC/media.tar.gz"
  echo "    медиа: $($DC exec -T backend sh -c 'du -sh /app/media | cut -f1' 2>/dev/null)"
else
  echo "    !! media.tar.gz не найден в $SRC — пропускаю (перенесите медиа отдельно)"
fi

echo "==> 4/5. Миграции (no-op, если структура уже накатана) + collectstatic"
$DC up -d backend
sleep 3
$DC exec -T backend python manage.py migrate --noinput | sed 's/^/    /'
$DC exec -T backend python manage.py collectstatic --noinput | tail -3 | sed 's/^/    /'

echo "==> 5/5. Запуск всех сервисов + health-check"
$DC up -d
code="000"
for _ in $(seq 1 20); do
  sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8003/api/v1/" || echo "000")
  [ "$code" != "000" ] && [ "${code:0:1}" != "5" ] && break
done
echo "    GET :8003/api/v1/ -> HTTP $code"

echo
echo "==> ГОТОВО. Проверьте через домен (после DNS+TLS): https://menugen.ru/"
echo "    Смоук-тест: логин, генерация меню, открытие рецепта, фото «я приготовил», /admin/."
