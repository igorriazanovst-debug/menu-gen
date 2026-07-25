#!/usr/bin/env bash
# MenuGen: безопасный аддитивный деплой BACKEND (код + миграции + рестарт).
#
# Философия — как у deploy_web.sh: код берём из ветки в ИЗОЛИРОВАННОМ git
# worktree и rsync'им ТОЛЬКО каталог backend/ в рабочее дерево. Основное дерево
# ($REPO) не переключаем (никаких `git checkout` всей репы → web-dist/.env целы).
#
# Перед изменениями делаем бэкап БД (pg_dump) и бэкап текущего backend/, поэтому
# деплой полностью обратим. Миграции этой ветки — аддитивные (AddField с
# default/nullable, AddIndex): существующие данные не трогаются.
#
# Запуск (на сервере):
#   cd /opt/menugen
#   git fetch origin claude/nifty-rubin-h90pfg
#   git show origin/claude/nifty-rubin-h90pfg:scripts/deploy_backend.sh > /tmp/deploy_backend.sh
#   sed -i 's/\r$//' /tmp/deploy_backend.sh    # на случай CRLF
#   chmod +x /tmp/deploy_backend.sh
#   /tmp/deploy_backend.sh                      # покажет план миграций и спросит подтверждение
#   # неинтерактивно:  ASSUME_YES=1 /tmp/deploy_backend.sh
#
# Откат:
#   - код:  tar -C "$REPO" -xzf backups/backend.tar.gz.bak_<TS>
#   - БД:   gunzip -c backups/db.sql.gz.bak_<TS> | docker compose exec -T db \
#             psql -U "$DB_USER" -d "$DB_NAME"
#   затем  docker compose restart backend celery celery-beat
set -euo pipefail

REPO=/opt/menugen
BRANCH=${BRANCH:-claude/nifty-rubin-h90pfg}
WT=/tmp/mg-backend-build           # изолированная копия ветки (worktree)
TS=$(date +%Y%m%d_%H%M%S)
# URL для health-check после рестарта. dev/старый: nginx на :8081. Прод
# (menugen.ru): nginx на 80/443, backend напрямую на 127.0.0.1:8003 —
# переопредели:  HEALTH_URL=http://127.0.0.1:8003/api/v1/ BRANCH=main ...
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:8081/api/v1/}

cd "$REPO"

# docker compose v2 («docker compose») или v1 («docker-compose»).
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "!! Не найден docker compose / docker-compose"; exit 1
fi

MAINBR=$(git rev-parse --abbrev-ref HEAD)
echo "==> Основное дерево остаётся на ветке: $MAINBR (web-dist/.env не трогаем)"
echo "==> Compose: $DC"

# .env с DB_NAME/DB_USER/... лежит в корне репозитория.
# shellcheck disable=SC1091
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a
DB_NAME=${DB_NAME:-menugen}
DB_USER=${DB_USER:-menugen}

mkdir -p "$REPO/backups"

echo "==> 0a. Бэкап БД (pg_dump)"
$DC exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$REPO/backups/db.sql.gz.bak_${TS}"
echo "    $REPO/backups/db.sql.gz.bak_${TS}"

echo "==> 0b. Бэкап текущего backend/"
tar -C "$REPO" --exclude='backend/media' -czf "$REPO/backups/backend.tar.gz.bak_${TS}" backend/
echo "    $REPO/backups/backend.tar.gz.bak_${TS}"

echo "==> 1. Фетч ветки backend: $BRANCH"
git fetch origin "$BRANCH"

echo "==> 2. Изолированный worktree из origin/$BRANCH"
git worktree remove --force "$WT" 2>/dev/null || true
rm -rf "$WT"
git worktree add --detach "$WT" "origin/$BRANCH"

cleanup() {
  echo "==> Чистка worktree"
  cd "$REPO"
  git worktree remove --force "$WT" 2>/dev/null || true
  rm -rf "$WT"
}
trap cleanup EXIT

echo "==> 3. Синхронизация кода backend/ (без media и кэшей)"
# media/ — отдельный docker volume (/app/media), .env — в корне, их не трогаем.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude='media/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$WT/backend/" "$REPO/backend/"
else
  echo "    rsync не найден — синхронизация через tar (mirror, media сохраняется)"
  # Удаляем всё в backend/, кроме media/, затем распаковываем код из ветки.
  find "$REPO/backend" -mindepth 1 -maxdepth 1 ! -name media -exec rm -rf {} +
  tar -C "$WT/backend" --exclude='media' --exclude='__pycache__' --exclude='*.pyc' -cf - . \
    | tar -C "$REPO/backend" -xf -
fi

echo "==> 4. План миграций (что будет применено)"
$DC exec -T backend python manage.py migrate --plan | sed 's/^/    /'

if [ "${ASSUME_YES:-0}" != "1" ]; then
  printf '==> Применить миграции и перезапустить backend? [y/N] '
  read -r ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "!! Отменено пользователем. Код уже синхронизирован, миграции НЕ применены."; \
       echo "!! Откат кода при необходимости: tar -C $REPO -xzf backups/backend.tar.gz.bak_${TS}"; \
       exit 1;;
  esac
fi

echo "==> 5. Применение миграций"
$DC exec -T backend python manage.py migrate --noinput

echo "==> 6. Рестарт backend + celery + celery-beat"
$DC restart backend celery celery-beat

echo "==> 7. Health-check API"
# runserver после рестарта поднимается не мгновенно — ретраим до ~40с,
# чтобы не получить ложный 502 от nginx, пока Django ещё стартует.
code="000"
for _ in $(seq 1 20); do
  sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || echo "000")
  # Любой ответ кроме 000/5xx означает, что Django поднялся (401/404/200 — ок).
  if [ "$code" != "000" ] && [ "${code:0:1}" != "5" ]; then
    break
  fi
done
echo "    GET /api/v1/ -> HTTP $code"
if [ "$code" = "000" ] || [ "${code:0:1}" = "5" ]; then
  echo "!! Backend не отвечает корректно (HTTP $code) после ожидания. Проверь логи:"
  echo "     $DC logs --tail=80 backend"
  echo "!! Откат: см. шапку скрипта (backend.tar.gz.bak_${TS} + db.sql.gz.bak_${TS})."
  exit 1
fi

echo "==> ГОТОВО. Backend задеплоен с ветки $BRANCH."
echo "    Бэкапы: backups/db.sql.gz.bak_${TS}, backups/backend.tar.gz.bak_${TS}"
