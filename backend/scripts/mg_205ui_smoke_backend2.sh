#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_smoke_backend2.sh
# MG-205-UI smoke v2: curl выполняется ВНУТРИ контейнера backend.
set -euo pipefail

ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
DC="docker compose -f $ROOT/docker-compose.yml"

echo "=== MG-205-UI SMOKE BACKEND v2 @ $TS ==="

# ─────── 1) Bootstrap test user & JWT ───────
echo ""
echo "── 1) Bootstrap test user & JWT ──"
JWT_ACCESS=$($DC exec -T backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import Profile

User = get_user_model()
EMAIL = 'mg205ui_smoke@test.local'

u, created = User.objects.get_or_create(email=EMAIL, defaults={'name': 'Smoke 205UI'})
if created:
    u.set_password('xx'); u.save()

p, _ = Profile.objects.get_or_create(user=u, defaults={
    'birth_year': 1990,
    'gender': Profile.Gender.MALE,
    'height_cm': 180,
    'weight_kg': Decimal('75'),
    'activity_level': Profile.ActivityLevel.MODERATE,
    'goal': Profile.Goal.MAINTAIN,
})

# Принудительно — запись аудита для всех 5 полей (если их нет)
from apps.users.audit import record_target_change
for f in ('calorie_target','protein_target_g','fat_target_g','carb_target_g','fiber_target_g'):
    if not p.target_audits.filter(field=f).exists():
        record_target_change(profile=p, field=f, new_value=getattr(p, f),
                             source='auto', by_user=None, old_value=None,
                             reason='smoke bootstrap')

print(str(RefreshToken.for_user(u).access_token))
" 2>/dev/null | tail -1)

if [ -z "$JWT_ACCESS" ] || [ ${#JWT_ACCESS} -lt 50 ]; then
  echo "ERROR: cannot get JWT, aborting smoke"; exit 1
fi
echo "  JWT acquired (len=${#JWT_ACCESS})"

# ─────── 2) Определяем backend URL ВНУТРИ контейнера ───────
# Django dev обычно слушает 0.0.0.0:8000 → внутри localhost:8000.
BASE=http://localhost:8000/api/v1

# Утилита для curl внутри контейнера
incurl() {
  $DC exec -T backend curl -sS -w '\n__HTTP_CODE__:%{http_code}\n' "$@"
}

incurl_pretty() {
  local out; out=$(incurl "$@")
  local code; code=$(echo "$out" | grep -oE '__HTTP_CODE__:[0-9]+' | head -1 | cut -d: -f2)
  local body; body=$(echo "$out" | sed '/__HTTP_CODE__:/d')
  echo "  HTTP $code"
  echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
}

H="Authorization: Bearer $JWT_ACCESS"

echo ""
echo "── 2) GET /users/me/ — profile.targets_meta? ──"
RESP=$(incurl -H "$H" "$BASE/users/me/" | sed '/__HTTP_CODE__:/d')
echo "$RESP" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read() or '{}')
meta = (data.get('profile') or {}).get('targets_meta')
if meta:
    print(json.dumps(meta, indent=2, ensure_ascii=False))
else:
    print('NO targets_meta found! profile keys:', list((data.get('profile') or {}).keys()))
"

echo ""
echo "── 3) GET /users/me/targets/protein_target_g/history/ ──"
incurl_pretty -H "$H" "$BASE/users/me/targets/protein_target_g/history/" | head -40

echo ""
echo "── 4) PATCH /users/me/  →  user override (protein=180.0) ──"
RESP=$(incurl -H "$H" -H "Content-Type: application/json" \
       -X PATCH -d '{"profile":{"protein_target_g":"180.0"}}' "$BASE/users/me/" \
       | sed '/__HTTP_CODE__:/d')
echo "$RESP" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read() or '{}')
p = d.get('profile') or {}
m = (p.get('targets_meta') or {}).get('protein_target_g')
print(f'  protein val = {p.get(\"protein_target_g\")}')
print(f'  protein meta = {json.dumps(m, ensure_ascii=False)}')
"

echo ""
echo "── 5) GET history после override ──"
incurl -H "$H" "$BASE/users/me/targets/protein_target_g/history/" \
  | sed '/__HTTP_CODE__:/d' \
  | python3 -c "
import json, sys
arr = json.loads(sys.stdin.read() or '[]')
print(f'  total: {len(arr)} entries')
for e in arr[:5]:
    print(f\"  - {e['at']}  src={e['source']:10s}  old={e['old_value']}  new={e['new_value']}  by={e.get('by_user')}\")
"

echo ""
echo "── 6) POST reset/protein_target_g/ ──"
RESP=$(incurl -H "$H" -X POST "$BASE/users/me/targets/protein_target_g/reset/" \
       | sed '/__HTTP_CODE__:/d')
echo "$RESP" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read() or '{}')
p = d.get('profile') or {}
m = (p.get('targets_meta') or {}).get('protein_target_g')
print(f'  protein val (after reset) = {p.get(\"protein_target_g\")}')
print(f'  protein meta = {json.dumps(m, ensure_ascii=False)}')
"

echo ""
echo "── 7) Validation: bad field name ──"
incurl -H "$H" "$BASE/users/me/targets/invalid_field/history/" \
  | tee /tmp/mg205ui_bad.txt > /dev/null
grep -E '__HTTP_CODE__|field' /tmp/mg205ui_bad.txt | head -5

echo ""
echo "── 8) Family: GET /family/ + targets_meta? ──"
RESP=$(incurl -H "$H" "$BASE/family/" | sed '/__HTTP_CODE__:/d')
echo "$RESP" > /tmp/mg205ui_family.json
python3 <<'PYEOF'
import json
d = json.load(open('/tmp/mg205ui_family.json'))
print('family:', d.get('name'))
for m in d.get('members', []):
    p = m.get('profile') or {}
    meta = p.get('targets_meta')
    print(f"  member id={m['id']} name={m['name']!r}  email={m.get('email')}  meta? {'YES' if meta else 'NO'}")
    if meta:
        print('   →', json.dumps({k: v.get('source') for k, v in meta.items()}, ensure_ascii=False))
PYEOF

# Member id текущего юзера
MEMBER_ID=$(python3 -c "
import json
d = json.load(open('/tmp/mg205ui_family.json'))
for m in d.get('members', []):
    if m.get('email') == 'mg205ui_smoke@test.local':
        print(m['id']); break
")

if [ -n "${MEMBER_ID:-}" ]; then
    echo ""
    echo "── 9) Family member history (member_id=$MEMBER_ID) ──"
    incurl -H "$H" "$BASE/family/members/$MEMBER_ID/targets/calorie_target/history/" \
      | sed '/__HTTP_CODE__:/d' \
      | python3 -c "
import json, sys
arr = json.loads(sys.stdin.read() or '[]')
print(f'  total: {len(arr)} entries')
for e in arr[:5]:
    print(f\"  - src={e['source']:10s}  new={e['new_value']}  reason={e.get('reason','')[:40]}\")
"

    echo ""
    echo "── 10) Family member RESET protein_target_g ──"
    incurl -H "$H" -X POST "$BASE/family/members/$MEMBER_ID/targets/protein_target_g/reset/" \
      | sed '/__HTTP_CODE__:/d' \
      | python3 -c "
import json, sys
m = json.loads(sys.stdin.read() or '{}')
p = m.get('profile') or {}
meta = (p.get('targets_meta') or {}).get('protein_target_g')
print(f'  protein val = {p.get(\"protein_target_g\")}')
print(f'  protein meta = {json.dumps(meta, ensure_ascii=False)}')
"
fi

echo ""
echo "=== SMOKE v2 DONE @ $TS ==="
