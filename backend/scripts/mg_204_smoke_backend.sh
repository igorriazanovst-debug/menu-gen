#!/usr/bin/env bash
# MG-204 backend smoke: PATCH /api/v1/family/members/{id}/update/
#
# Что проверяем:
# 1. PATCH с meal_plan_type='5' → 200 OK, в БД meal_plan_type=='5'
# 2. PATCH с meal_plan_type='3' (откат) → 200 OK
# 3. PATCH с target-полем (calorie_target) → 200 OK + в ProfileTargetAudit запись source='user'
# 4. После теста БД возвращена в исходное состояние (meal_plan_type='3', calorie_target=2077)
#
# Логин: admin@dev.local / какой-то pass — берём JWT через login API.

set -euo pipefail

DC="docker compose -f /opt/menugen/docker-compose.yml"
API="http://31.192.110.121:8081/api/v1"
EMAIL="admin@dev.local"

echo "=========================================="
echo "MG-204 BACKEND SMOKE: family member PATCH"
echo "=========================================="
echo

PASS="Admin1234!"

# ── 1. Логин: получаем JWT ───────────────────────────────────────────────────
echo "### 1. POST /auth/login/ → JWT ###"
LOGIN_RESP=$(curl -s -X POST "${API}/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASS}\"}")
echo "  raw: ${LOGIN_RESP}" | head -c 400
echo
ACCESS=$(echo "${LOGIN_RESP}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access',''))")
if [ -z "$ACCESS" ]; then
  echo "  ❌ Не получили access token. Прерываю."
  exit 1
fi
echo "  access: ${ACCESS:0:40}..."
echo

H="Authorization: Bearer ${ACCESS}"

# ── 2. GET /family/ — найти member.id для admin ──────────────────────────────
echo "### 2. GET /family/ → member.id ###"
FAMILY_JSON=$(curl -s "${API}/family/" -H "$H")
echo "$FAMILY_JSON" | python3 -m json.tool | head -40
echo
MEMBER_ID=$(echo "$FAMILY_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
me = next((m for m in d.get('members',[]) if m.get('email')=='${EMAIL}'), None)
print(me['id'] if me else '')
")
if [ -z "$MEMBER_ID" ]; then
  echo "  ❌ member для ${EMAIL} не найден"
  exit 1
fi
echo "  member.id = $MEMBER_ID"
echo

# ── 3. Сохраняем исходное состояние ──────────────────────────────────────────
echo "### 3. Исходное состояние Profile + audit count ###"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User, ProfileTargetAudit
u = User.objects.get(email='${EMAIL}')
p = u.profile
print(f'BEFORE: calorie={p.calorie_target} mp={p.meal_plan_type}')
print(f'AUDIT count: {ProfileTargetAudit.objects.filter(profile=p).count()}')
" 2>&1 | grep -v "warning"
echo

# ── 4. Шаг 1: PATCH meal_plan_type=5 ─────────────────────────────────────────
echo "### 4. PATCH meal_plan_type='5' ###"
RESP=$(curl -s -w "\nHTTP:%{http_code}" -X PATCH \
  "${API}/family/members/${MEMBER_ID}/update/" \
  -H "$H" -H "Content-Type: application/json" \
  -d '{"profile":{"meal_plan_type":"5"}}')
echo "$RESP"
HTTP=$(echo "$RESP" | grep '^HTTP:' | cut -d: -f2)
[ "$HTTP" = "200" ] && echo "  ✅ 200 OK" || { echo "  ❌ HTTP $HTTP"; }
echo

echo "  → проверка в БД:"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User
u = User.objects.get(email='${EMAIL}')
p = u.profile
print(f'AFTER PATCH 1: meal_plan_type={p.meal_plan_type}')
assert p.meal_plan_type=='5', f'expected 5, got {p.meal_plan_type}'
print('  ✅ DB: meal_plan_type==5')
" 2>&1 | grep -v "warning"
echo

# ── 5. Шаг 2: PATCH meal_plan_type=3 (откат) ─────────────────────────────────
echo "### 5. PATCH meal_plan_type='3' (откат) ###"
RESP=$(curl -s -w "\nHTTP:%{http_code}" -X PATCH \
  "${API}/family/members/${MEMBER_ID}/update/" \
  -H "$H" -H "Content-Type: application/json" \
  -d '{"profile":{"meal_plan_type":"3"}}')
HTTP=$(echo "$RESP" | grep '^HTTP:' | cut -d: -f2)
[ "$HTTP" = "200" ] && echo "  ✅ 200 OK" || { echo "  ❌ HTTP $HTTP"; echo "$RESP"; }
echo

# ── 6. Шаг 3: PATCH calorie_target=1900 → проверяем audit с source='user' ────
echo "### 6. PATCH calorie_target=1900 → audit source='user' ###"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User, ProfileTargetAudit
u = User.objects.get(email='${EMAIL}')
p = u.profile
ProfileTargetAudit.objects.filter(profile=p).delete()  # очистка для чистоты
print('audit cleared')
" 2>&1 | grep -v "warning"

RESP=$(curl -s -w "\nHTTP:%{http_code}" -X PATCH \
  "${API}/family/members/${MEMBER_ID}/update/" \
  -H "$H" -H "Content-Type: application/json" \
  -d '{"profile":{"calorie_target":1900}}')
echo "$RESP"
HTTP=$(echo "$RESP" | grep '^HTTP:' | cut -d: -f2)
[ "$HTTP" = "200" ] && echo "  ✅ 200 OK" || { echo "  ❌ HTTP $HTTP"; }
echo

echo "  → проверка в БД + audit:"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User, ProfileTargetAudit
from apps.users.audit import get_field_source
u = User.objects.get(email='${EMAIL}')
p = u.profile
print(f'calorie_target = {p.calorie_target}')
print(f'source(calorie_target) = {get_field_source(p, \"calorie_target\")}')
audit = ProfileTargetAudit.objects.filter(profile=p, field='calorie_target').order_by('-at')
for a in audit[:3]:
    print(f'  audit: source={a.source} new={a.new_value} old={a.old_value} by={a.by_user_id}')
src = get_field_source(p, 'calorie_target')
assert src == 'user', f'expected source=user, got {src}'
print('  ✅ source==user, audit записан')
" 2>&1 | grep -v "warning"
echo

# ── 7. Откат: возвращаем calorie_target=2077 через force=True (auto) ─────────
echo "### 7. Откат calorie_target → 2077 (force=True, source=auto) ###"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User
from apps.users.nutrition import fill_profile_targets
u = User.objects.get(email='${EMAIL}')
p = u.profile
fill_profile_targets(p, force=True, actor=None)
p.save()
print(f'AFTER reset: calorie={p.calorie_target} mp={p.meal_plan_type}')
" 2>&1 | grep -v "warning"
echo

echo "=========================================="
echo "MG-204 SMOKE DONE"
echo "=========================================="
