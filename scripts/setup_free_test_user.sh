#!/usr/bin/env bash
# MenuGen: создать тестового Free-юзера и проверить freemium-квоту.
#
# Запускать ПОСЛЕ scripts/deploy_backend.sh (нужны миграции 0002/0003 и
# management-команда create_test_free_user из ветки).
#
# Запуск (на сервере):
#   cd /opt/menugen
#   git fetch origin main
#   git show origin/main:scripts/setup_free_test_user.sh > /tmp/sftu.sh
#   sed -i 's/\r$//' /tmp/sftu.sh
#   bash /tmp/sftu.sh
#   # переопределить логин/пароль: EMAIL=foo@bar PASSWORD='1234!' bash /tmp/sftu.sh
set -uo pipefail

REPO=/opt/menugen
cd "$REPO"

if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

EMAIL=${EMAIL:-free@menugen.test}
PASSWORD=${PASSWORD:-1234!}

echo "==> 1. Создаю/обновляю Free-юзера: $EMAIL"
$DC exec -T backend python manage.py create_test_free_user --email "$EMAIL" --password "$PASSWORD"

echo "==> 2. План free в БД:"
$DC exec -T backend python manage.py shell -c \
  "from apps.subscriptions.models import SubscriptionPlan as P; print('   plans:', list(P.objects.values_list('code','price','max_family_members')))"

echo "==> 3. Квота через API"
login() {
  curl -s "$1/auth/login/" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access",""))' 2>/dev/null
}
API=${API:-http://127.0.0.1:8081/api/v1}
TOKEN=$(login "$API")
if [ -z "$TOKEN" ]; then
  echo "   (через $API не вышло — пробую напрямую :8003)"
  API=http://127.0.0.1:8003/api/v1
  TOKEN=$(login "$API")
fi
if [ -z "$TOKEN" ]; then
  echo "   !! Логин не прошёл. Юзер создан? Backend поднят? Миграции применены?"
  exit 1
fi
curl -s "$API/users/me/" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("   menu_quota:", d["subscription_status"]["menu_quota"])'

echo "==> ГОТОВО. Логин для веба и APK: $EMAIL / $PASSWORD"
