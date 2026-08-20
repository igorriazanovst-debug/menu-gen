#!/usr/bin/env bash
# MG_DEVMIRROR — развернуть снимок прода на DEV. Запускать НА DEV-сервере.
#
#   cd /opt/menugen
#   bash deploy/mirror/restore_dev.sh /opt/menugen/backups/mirror/<TS>
#
# Порядок намеренно такой: сначала проверки .env, потом бэкап текущего dev,
# и только затем восстановление. Данные прода не должны оказаться в контуре,
# который умеет писать живым людям или ходить в боевую кассу, — поэтому проверки
# идут ДО заливки, а не после.
set -euo pipefail

REPO=${REPO:-/opt/menugen}
SRC=${1:-}

if [ -z "$SRC" ] || [ ! -f "$SRC/menugen.dump" ]; then
  echo "!! Использование: bash restore_dev.sh <каталог со снимком (menugen.dump)>"
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

# ── 0. Проверки контура ──────────────────────────────────────────────────────
echo "==> 0/7. Проверяю, что это dev и что каналы наружу закрыты"
FATAL=""

[ "${MENUGEN_ENV:-}" = "dev" ] || FATAL="$FATAL\n    MENUGEN_ENV=${MENUGEN_ENV:-<не задан>} — нужен 'dev' (это же и защита sanitize_dev)"

case "${EMAIL_BACKEND:-}" in
  *console*|*dummy*|*locmem*) ;;
  *) FATAL="$FATAL\n    EMAIL_BACKEND=${EMAIL_BACKEND:-<не задан>} — на dev нужен console/dummy, иначе письма уйдут живым адресатам" ;;
esac

[ "${PAYMENTS_STUB:-}" = "True" ] || FATAL="$FATAL\n    PAYMENTS_STUB=${PAYMENTS_STUB:-<не задан>} — на dev нужен True"
[ -z "${YOOKASSA_SECRET_KEY:-}" ] || FATAL="$FATAL\n    YOOKASSA_SECRET_KEY задан — боевой ключ кассы на dev недопустим"
[ -z "${TELEGRAM_BOT_TOKEN:-}" ] || FATAL="$FATAL\n    TELEGRAM_BOT_TOKEN задан — бот с dev напишет живым людям"
[ -z "${MAX_BOT_TOKEN:-}" ]      || FATAL="$FATAL\n    MAX_BOT_TOKEN задан — то же самое"

if [ -n "$FATAL" ]; then
  echo "!! Остановлено. В $REPO/.env нужно поправить:"
  printf "$FATAL\n"
  echo
  echo "   Образец безопасного dev-хвоста .env — deploy/mirror/dev.env.sample"
  exit 1
fi
echo "    контур dev, почта в лог, оплата заглушкой, боевых ключей нет"

# ── 1. Бэкап текущего dev ────────────────────────────────────────────────────
TS=$(date +%Y%m%d_%H%M%S)
BAK="$REPO/backups/mirror/dev_before_$TS.dump"
mkdir -p "$REPO/backups/mirror"
echo "==> 1/7. Бэкап текущей базы dev → $BAK"
$DC exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BAK"
# Пустой бэкап — это не бэкап: откат, который печатается в конце, был бы
# фикцией, а восстановление затирает базу dev целиком.
BAK_SIZE=$(wc -c < "$BAK")
if [ "$BAK_SIZE" -lt 1000 ]; then
  echo "!! Бэкап базы dev пуст ($BAK_SIZE байт) — pg_dump не отработал. Не заливаю."
  exit 1
fi
echo "    $(du -h "$BAK" | cut -f1)"

# ── 2. Восстановление БД ─────────────────────────────────────────────────────
echo "==> 2/7. Останавливаю backend/celery и восстанавливаю базу"
$DC stop backend celery celery-beat 2>/dev/null || true
$DC up -d db redis
for _ in $(seq 1 30); do
  $DC exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  sleep 2
done
$DC exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner \
  < "$SRC/menugen.dump" 2>&1 | grep -vE 'does not exist, skipping' | sed 's/^/    /' || true

# ── 3. Медиа ─────────────────────────────────────────────────────────────────
echo "==> 3/7. Медиа"
$DC up -d backend
sleep 3
if [ -f "$SRC/media.tar.gz" ]; then
  $DC exec -T backend sh -c 'find /app/media -mindepth 1 -delete 2>/dev/null; mkdir -p /app/media' || true
  $DC exec -T backend tar -C /app -xzf - < "$SRC/media.tar.gz"
  echo "    $($DC exec -T backend sh -c 'du -sh /app/media | cut -f1' 2>/dev/null)"
else
  echo "    media.tar.gz в снимке нет — картинки будут битыми, это ожидаемо (WITH_MEDIA=0)"
fi

# ── 4. Миграции ──────────────────────────────────────────────────────────────
echo "==> 4/7. Миграции (код dev может быть новее снимка)"
$DC exec -T backend python manage.py migrate --noinput | sed 's/^/    /'

# ── 5. Обезличивание ─────────────────────────────────────────────────────────
echo "==> 5/7. Обезличивание боевых данных"
KEEP=${KEEP_EMAILS:-}
$DC exec -T backend python manage.py sanitize_dev --yes ${KEEP:+--keep-emails "$KEEP"} | sed 's/^/    /'

# ── 6. Ссылки на медиа и статика ─────────────────────────────────────────────
echo "==> 6/7. Ссылки на медиа → относительные, collectstatic"
$DC exec -T backend python manage.py normalize_media_urls --apply | tail -5 | sed 's/^/    /'
$DC exec -T backend python manage.py collectstatic --noinput | tail -2 | sed 's/^/    /'

# ── 7. Подъём и проверка ─────────────────────────────────────────────────────
echo "==> 7/7. Запуск и health-check"
$DC up -d
# Дёргаем настоящий эндпоинт, а не корень API: корень отдаёт 404 и на рабочем
# приложении, и на сломанном — по нему видно только, что Django жив. Список
# тарифов открыт без авторизации и лезет в базу: 200 означает, что связка
# «приложение + восстановленная база» работает.
HEALTH_URL="http://127.0.0.1:8003/api/v1/subscriptions/plans/"
code="000"
for _ in $(seq 1 20); do
  sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || echo "000")
  [ "$code" = "200" ] && break
done
echo "    GET /api/v1/subscriptions/plans/ -> HTTP $code"
if [ "$code" != "200" ]; then
  echo "    !! Ожидался 200. Зеркало залито, но приложение отвечает не так — смотри:"
  echo "       $DC logs --tail=50 backend"
fi

echo
echo "==> ГОТОВО. Откат к прежнему состоянию dev:"
echo "     $DC exec -T db pg_restore -U $DB_USER -d $DB_NAME --clean --if-exists --no-owner < $BAK"
