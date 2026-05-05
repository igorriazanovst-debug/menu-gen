#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_smoke_backend.sh
# MG-205-UI этап B: проверка маршрутов + curl GET history / POST reset.
set -euo pipefail

ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
DC="docker compose -f $ROOT/docker-compose.yml"

echo "=== MG-205-UI SMOKE BACKEND @ $TS ==="

# ─────── 1) Маршруты ───────
echo ""
echo "── 1) URL routes ──"
$DC exec -T backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.urls import get_resolver
def walk(r, prefix=''):
    for p in r.url_patterns:
        if hasattr(p, 'url_patterns'):
            walk(p, prefix + str(p.pattern))
        else:
            full = prefix + str(p.pattern)
            if 'target' in full or 'users/me' in full or 'family/members' in full:
                print(full)
walk(get_resolver())
" 2>&1 | sort -u

# ─────── 2) Существующие тесты MG-205 не сломались ───────
echo ""
echo "── 2) pytest test_mg_205.py ──"
$DC exec -T backend pytest apps/users/tests/test_mg_205.py -v --no-header 2>&1 | tail -30

# ─────── 3) Создаём тест-юзера и токен ───────
echo ""
echo "── 3) Bootstrap test user & JWT ──"
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

# Принудительно убедимся что есть аудит-записи (auto)
from apps.users.audit import record_target_change, get_field_source
for f in ('calorie_target', 'protein_target_g', 'fat_target_g', 'carb_target_g', 'fiber_target_g'):
    if not p.target_audits.filter(field=f).exists():
        record_target_change(profile=p, field=f, new_value=getattr(p, f),
                             source='auto', by_user=None, old_value=None,
                             reason='smoke bootstrap')

print(str(RefreshToken.for_user(u).access_token))
" 2>/dev/null | tail -1)

if [ -z "$JWT_ACCESS" ] || [ ${#JWT_ACCESS} -lt 50 ]; then
  echo "ERROR: cannot get JWT, aborting smoke"
  exit 1
fi
echo "  JWT acquired (len=${#JWT_ACCESS})"

# ─────── 4) Bearer URL ───────
BASE=http://localhost:8000/api/v1
H="Authorization: Bearer $JWT_ACCESS"

echo ""
echo "── 4) GET /users/me/ — должен содержать profile.targets_meta ──"
curl -sf -H "$H" "$BASE/users/me/" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
meta = (data.get('profile') or {}).get('targets_meta')
print(json.dumps(meta, indent=2, ensure_ascii=False) if meta else 'NO targets_meta!')
"

echo ""
echo "── 5) GET /users/me/targets/protein_target_g/history/ ──"
curl -sf -H "$H" "$BASE/users/me/targets/protein_target_g/history/" \
  | python3 -m json.tool | head -30

echo ""
echo "── 6) PATCH /users/me/  →  user override (protein=180) ──"
curl -sf -H "$H" -H "Content-Type: application/json" \
  -X PATCH "$BASE/users/me/" \
  -d '{"profile":{"protein_target_g":"180.0"}}' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
meta = (data.get('profile') or {}).get('targets_meta', {})
print('protein meta:', json.dumps(meta.get('protein_target_g'), indent=2, ensure_ascii=False))
print('protein val:', data['profile'].get('protein_target_g'))
"

echo ""
echo "── 7) GET history после override (должна быть запись source=user) ──"
curl -sf -H "$H" "$BASE/users/me/targets/protein_target_g/history/" \
  | python3 -c "
import json, sys
arr = json.load(sys.stdin)
print(f'  total: {len(arr)} entries')
for e in arr[:3]:
    print(f\"  - {e['at']}  src={e['source']:10s}  old={e['old_value']}  new={e['new_value']}  by={e.get('by_user')}\")
"

echo ""
echo "── 8) POST reset/protein_target_g/  → авторасчёт + source=auto ──"
curl -sf -H "$H" -H "Content-Type: application/json" \
  -X POST "$BASE/users/me/targets/protein_target_g/reset/" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
meta = (data.get('profile') or {}).get('targets_meta', {})
print('protein val:', data['profile'].get('protein_target_g'))
print('protein meta:', json.dumps(meta.get('protein_target_g'), indent=2, ensure_ascii=False))
"

echo ""
echo "── 9) Validation: bad field name ──"
HTTP_CODE=$(curl -s -o /tmp/mg205ui_err.json -w '%{http_code}' \
  -H "$H" "$BASE/users/me/targets/invalid_field/history/")
echo "  status=$HTTP_CODE"
cat /tmp/mg205ui_err.json | python3 -m json.tool 2>/dev/null || cat /tmp/mg205ui_err.json
echo ""

echo ""
echo "── 10) Family: GET /family/ — members[].profile.targets_meta ──"
FAMILY_RESP=$(curl -sf -H "$H" "$BASE/family/")
echo "$FAMILY_RESP" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print('family:', data.get('name'))
for m in data.get('members', []):
    p = m.get('profile') or {}
    meta = p.get('targets_meta')
    print(f\"  member id={m['id']} name={m['name']!r}  meta? {'YES' if meta else 'NO'}\")
    if meta:
        print('   →', json.dumps({k: v.get('source') for k, v in meta.items()}, ensure_ascii=False))
"

# Получаем member_id текущего юзера в его семье
MEMBER_ID=$(echo "$FAMILY_RESP" | python3 -c "
import json, sys
d = json.load(sys.stdin)
me_email = '$1' if len(sys.argv) > 1 else 'mg205ui_smoke@test.local'
for m in d.get('members', []):
    if m.get('email') == 'mg205ui_smoke@test.local':
        print(m['id']); break
")

if [ -n "$MEMBER_ID" ]; then
    echo ""
    echo "── 11) Family member history ($MEMBER_ID) ──"
    curl -sf -H "$H" "$BASE/family/members/$MEMBER_ID/targets/calorie_target/history/" \
      | python3 -c "
import json, sys
arr = json.load(sys.stdin)
print(f'  total: {len(arr)} entries')
for e in arr[:3]:
    print(f\"  - src={e['source']:10s}  new={e['new_value']}\")
"

    echo ""
    echo "── 12) Family member RESET protein ──"
    curl -sf -H "$H" -H "Content-Type: application/json" \
      -X POST "$BASE/family/members/$MEMBER_ID/targets/protein_target_g/reset/" \
      | python3 -c "
import json, sys
m = json.load(sys.stdin)
p = m.get('profile') or {}
meta = p.get('targets_meta', {})
print('protein val:', p.get('protein_target_g'))
print('protein src:', meta.get('protein_target_g', {}).get('source'))
"
fi

echo ""
echo "=== SMOKE DONE @ $TS ==="
