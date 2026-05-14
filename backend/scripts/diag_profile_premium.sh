#!/usr/bin/env bash
# DIAG: MG-profile-premium
# Расположение: /opt/menugen/backend/scripts/diag_profile_premium.sh
# Запуск:        bash /opt/menugen/backend/scripts/diag_profile_premium.sh 2>&1 | tee /tmp/diag_profile_premium.log

set -u
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
MOBILE="${ROOT}/mobile/menugen_app"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── BACKEND ────────────────────────────────────────────────────────────────

hr "B1. apps/users/serializers.py — UserMeSerializer класс целиком"
awk '/^class UserMeSerializer/,/^class [A-Z]/' "${BACKEND}/apps/users/serializers.py" | head -80

hr "B2. apps/users/serializers.py — все классы Meta.fields (для контекста)"
grep -nE "^class |fields\s*=\s*\(" "${BACKEND}/apps/users/serializers.py" | head -40

hr "B3. apps/subscriptions/permissions.py — экспортируемые хелперы"
grep -nE "^def |^class " "${BACKEND}/apps/subscriptions/permissions.py"

hr "B4. apps/subscriptions/models.py — Subscription поля + Status choices"
grep -nE "^class |Status|=\s*models\." "${BACKEND}/apps/subscriptions/models.py" | head -40

hr "B5. apps/users/views.py — UserMeView"
awk '/^class UserMeView/,/^# /' "${BACKEND}/apps/users/views.py" | head -40

hr "B6. apps/users/tests — что уже есть (для размещения нового теста)"
ls -la "${BACKEND}/apps/users/tests/" 2>/dev/null | head -30

hr "B7. apps/users/tests — пример test_*.py с Family+Subscription (для шаблона)"
for f in "${BACKEND}/apps/users/tests/"test_*.py; do
  [ -f "$f" ] || continue
  if grep -q "Subscription\|Family.objects" "$f"; then
    echo "--- $f ---"
    grep -nE "import|Family\.objects|Subscription|@pytest|def setup|fixture" "$f" | head -25
  fi
done

hr "B8. Реальный JSON GET /users/me (через manage.py shell, без сети)"
docker compose -f "${ROOT}/docker-compose.yml" exec -T backend python manage.py shell -c "
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from apps.users.models import User
from apps.users.serializers import UserMeSerializer
import json

u = User.objects.filter(email='admin@dev.local').first()
if not u:
    u = User.objects.first()
if u:
    factory = APIRequestFactory()
    req = Request(factory.get('/'))
    req.user = u
    data = UserMeSerializer(u, context={'request': req}).data
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
else:
    print('no users in db')
" 2>&1 | head -60

hr "B9. Subscription model — реальные поля"
docker compose -f "${ROOT}/docker-compose.yml" exec -T backend python manage.py shell -c "
from apps.subscriptions.models import Subscription
print('Subscription fields:')
for f in Subscription._meta.get_fields():
    print(f'  {f.name}: {f.__class__.__name__}')
print()
print('Status choices:', dict(Subscription.Status.choices))
" 2>&1 | head -30

# ─── MOBILE ─────────────────────────────────────────────────────────────────

hr "M1. mobile dir exists?"
[ -d "$MOBILE" ] && echo "OK: $MOBILE" || { echo "MISSING: $MOBILE"; exit 0; }

hr "M2. Search for User/UserMe/Me model in mobile"
find "${MOBILE}/lib" -name "*.dart" | xargs grep -lE "class User\b|class UserMe\b|class Me\b|users/me" 2>/dev/null | head -10

hr "M3. AuthBloc / auth state / current user model"
find "${MOBILE}/lib/features/auth" -name "*.dart" 2>/dev/null | head -20
echo "---"
find "${MOBILE}/lib" -path "*auth*" -name "*.dart" 2>/dev/null | xargs grep -lE "/users/me|users/me/" 2>/dev/null

hr "M4. Все упоминания /users/me/ в mobile"
grep -rnE "/users/me|users/me/" "${MOBILE}/lib" 2>/dev/null | head -20

hr "M5. PremiumGateCubit — текущий state"
find "${MOBILE}/lib/core/premium" -name "*.dart" 2>/dev/null
echo "---"
cat "${MOBILE}/lib/core/premium/premium_gate_cubit.dart" 2>/dev/null | head -80

hr "M6. ProfileScreen — где будем рисовать badge"
find "${MOBILE}/lib/features/profile" -name "*.dart" 2>/dev/null
echo "---"
grep -nE "^class |Premium|Subscription|subscription_status" "${MOBILE}/lib/features/profile/screens/profile_screen.dart" 2>/dev/null | head -20

hr "M7. main.dart — wiring PremiumGateCubit"
grep -nE "PremiumGateCubit|bootstrap|BlocProvider" "${MOBILE}/lib/main.dart" 2>/dev/null | head -20

hr "M8. PaywallBanner — текущая логика показа"
cat "${MOBILE}/lib/core/premium/paywall_banner.dart" 2>/dev/null | head -60

echo
echo "=== diag finished ==="
