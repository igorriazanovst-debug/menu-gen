#!/usr/bin/env bash
# MenuGen — BOOTSTRAP НОВОГО сервера (158.255.5.166 / menugen.ru), Ubuntu 22.04+.
# Готовит приёмник ЗАРАНЕЕ, без простоя старого: docker + nginx + certbot, код,
# пустая БД со структурой, сборка веб-фронта. Данные накатим позже (import_new.sh).
#
# ВАЖНО: секреты (.env) заполняются ВРУЧНУЮ — берём со старого сервера. Скрипт
# останавливается и просит их, если .env отсутствует.
#
# Запуск на новом сервере (root):
#   apt-get update && apt-get install -y git
#   git clone <REPO_URL> /opt/menugen && cd /opt/menugen
#   git checkout main
#   bash deploy/migrate/bootstrap_new.sh
set -euo pipefail

REPO=${REPO:-/opt/menugen}
DOMAIN=${DOMAIN:-menugen.ru}
cd "$REPO"

echo "==> 1/7. Системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg git rsync ufw nginx \
  certbot python3-certbot-nginx

# Docker (официальный репозиторий)
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Устанавливаю Docker Engine + compose-plugin"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
DC="docker compose"

echo "==> 2/7. Firewall (ufw): 22, 80, 443"
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
yes | ufw enable || true

echo "==> 3/7. .env (профиль НОВЫЙ сервер)"
if [ ! -f "$REPO/.env" ]; then
  cp "$REPO/.env.example" "$REPO/.env"
  echo "!! Создан $REPO/.env из примера. ЗАПОЛНИТЕ секреты со старого сервера:"
  echo "     SECRET_KEY, DB_PASSWORD, AI_API_KEY (и AI_PROVIDER/AI_BASE_URL/AI_TEXT_MODEL),"
  echo "     EMAIL_* при наличии. И проставьте профиль НОВОГО сервера:"
  cat <<'HINT'
     DEBUG=False
     ALLOWED_HOSTS=menugen.ru,www.menugen.ru,127.0.0.1,localhost
     DB_NAME=menugen
     DB_USER=menugen_user
     BACKEND_BIND=127.0.0.1
     BACKEND_HOST_PORT=8003
     BACKEND_PUBLIC_URL=https://menugen.ru
     CORS_ALLOWED_ORIGINS=https://menugen.ru
     CSRF_TRUSTED_ORIGINS=https://menugen.ru,https://www.menugen.ru
     USE_X_FORWARDED_PROTO=True
     USE_X_FORWARDED_HOST=True
     SESSION_COOKIE_SECURE=True
     CSRF_COOKIE_SECURE=True
     REDIS_URL=redis://redis:6379/0
     CELERY_BROKER_URL=redis://redis:6379/0
     CELERY_RESULT_BACKEND=redis://redis:6379/0
HINT
  echo "!! Затем перезапустите: bash deploy/migrate/bootstrap_new.sh"
  exit 2
fi
echo "    .env найден — продолжаю."

echo "==> 4/7. Инфраструктура: db + redis"
$DC up -d db redis
for _ in $(seq 1 30); do
  set -a; . "$REPO/.env"; set +a
  if $DC exec -T db pg_isready -U "${DB_USER:-menugen_user}" -d "${DB_NAME:-menugen}" >/dev/null 2>&1; then break; fi
  sleep 2
done

echo "==> 5/7. Backend: структура БД (migrate) + collectstatic"
$DC up -d backend
sleep 4
$DC exec -T backend python manage.py migrate --noinput | sed 's/^/    /'
$DC exec -T backend python manage.py collectstatic --noinput | tail -3 | sed 's/^/    /'
$DC up -d   # celery, celery-beat

echo "==> 6/7. Веб-фронт (CRA -> web-dist, API_BASE_URL=/api/v1)"
WEBSRC="$REPO/web/menugen-web"
if [ ! -f "$WEBSRC/.env" ]; then
  echo "REACT_APP_API_BASE_URL=/api/v1" > "$WEBSRC/.env"
fi
# Node 20 LTS (NodeSource), если npm ещё нет.
if ! command -v npm >/dev/null 2>&1; then
  echo "    npm не найден — ставлю Node 20 LTS (NodeSource)"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
if command -v npm >/dev/null 2>&1; then
  ( cd "$WEBSRC" && npm install --legacy-peer-deps && CI=false npm run build )
  rm -rf "$REPO/web-dist" && mkdir -p "$REPO/web-dist"
  cp -a "$WEBSRC/build/." "$REPO/web-dist/"
  echo "    web-dist собран."
else
  echo "    !! Node/npm не поставился. Соберите фронт вручную (scripts/deploy_web.sh)"
  echo "       или перенесите готовый web-dist со старого сервера."
fi

echo "==> 7/7. nginx (HTTP-vhost; TLS добавит certbot после переключения DNS)"
cp "$REPO/deploy/nginx/${DOMAIN}.conf" "/etc/nginx/sites-available/${DOMAIN}.conf"
ln -sf "/etc/nginx/sites-available/${DOMAIN}.conf" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
rm -f /etc/nginx/sites-enabled/default || true
mkdir -p /var/www/certbot
if nginx -t 2>/dev/null; then
  systemctl reload nginx
  echo "    nginx перезагружен (HTTP). После DNS: certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
else
  echo "    !! nginx -t не прошёл — проверьте конфликты в sites-enabled:"
  echo "       nginx -t"
fi

echo
echo "==> BOOTSTRAP ГОТОВ. Новый сервер работает на пустой БД (проверка по IP)."
echo "    Дальше: DNS A-запись -> 158.255.5.166, затем import_new.sh + certbot (Фаза D)."
