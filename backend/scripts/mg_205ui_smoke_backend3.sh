#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_smoke_backend3.sh
# MG-205-UI smoke v3: HTTP вызовы через python urllib ВНУТРИ контейнера backend.
set -uo pipefail   # БЕЗ -e: иначе одна осечка прерывает весь скрипт

ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
DC="docker compose -f $ROOT/docker-compose.yml"

echo "=== MG-205-UI SMOKE v3 @ $TS ==="

# ─────── 0) Sanity ───────
echo "── 0) Containers up? ──"
$DC ps --format '{{.Name}} {{.State}}' 2>/dev/null | grep -E 'backend|db' || true

# ─────── 1) JWT ───────
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
    'birth_year': 1990, 'gender': Profile.Gender.MALE,
    'height_cm': 180, 'weight_kg': Decimal('75'),
    'activity_level': Profile.ActivityLevel.MODERATE,
    'goal': Profile.Goal.MAINTAIN,
})
from apps.users.audit import record_target_change
for f in ('calorie_target','protein_target_g','fat_target_g','carb_target_g','fiber_target_g'):
    if not p.target_audits.filter(field=f).exists():
        record_target_change(profile=p, field=f, new_value=getattr(p, f),
                             source='auto', by_user=None, old_value=None,
                             reason='smoke bootstrap')
print(str(RefreshToken.for_user(u).access_token))
" 2>/dev/null | tail -1)

if [ -z "${JWT_ACCESS:-}" ] || [ ${#JWT_ACCESS} -lt 50 ]; then
  echo "ERROR: cannot get JWT, aborting smoke"; exit 1
fi
echo "  JWT acquired (len=${#JWT_ACCESS})"

# ─────── 2) Inline pytest вместо curl ───────
# Вместо HTTP-запросов используем DRF APIClient — это даёт настоящий roundtrip
# через urlpatterns/views/serializers, но без сети.
echo ""
echo "── 2) DRF APIClient roundtrip (внутри контейнера) ──"

$DC exec -T -e JWT_ACCESS="$JWT_ACCESS" backend python <<'PYEOF'
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Подбираем валидный hostname под ALLOWED_HOSTS:
from django.conf import settings
ah = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])
if '*' in ah:
    HOST = 'localhost'
else:
    # выбираем первое непустое имя, иначе localhost
    HOST = next((h for h in ah if h and not h.startswith('.')), 'localhost')
print(f"   ALLOWED_HOSTS={ah!r}  → using SERVER_NAME={HOST!r}")

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.get(email='mg205ui_smoke@test.local')

c = APIClient(SERVER_NAME=HOST)
c.force_authenticate(user=u)


def show(title, resp):
    print()
    print(f"── {title} ── HTTP {resp.status_code}")
    body = resp.json() if resp.content else None
    return body


# 2.1) /users/me/ — есть targets_meta?
r = c.get('/api/v1/users/me/')
data = show("GET /users/me/", r)
meta = (data or {}).get('profile', {}).get('targets_meta')
if meta:
    for f, m in meta.items():
        print(f"   {f:18s}  src={m.get('source'):10s}  by={m.get('by_user')}  at={m.get('at')}")
else:
    print("   NO targets_meta!")

# 2.2) GET history
r = c.get('/api/v1/users/me/targets/protein_target_g/history/')
arr = show("GET history (protein, before override)", r)
print(f"   entries: {len(arr or [])}")
for e in (arr or [])[:3]:
    print(f"   - src={e['source']:10s}  old={e['old_value']}  new={e['new_value']}  by={e.get('by_user')}")

# 2.3) PATCH user override
r = c.patch('/api/v1/users/me/',
            data=json.dumps({'profile': {'protein_target_g': '180.0'}}),
            content_type='application/json')
data = show("PATCH /users/me/ (protein=180.0)", r)
p = (data or {}).get('profile') or {}
m = (p.get('targets_meta') or {}).get('protein_target_g') or {}
print(f"   protein val = {p.get('protein_target_g')}")
print(f"   protein src = {m.get('source')}  by={m.get('by_user')}")

# 2.4) GET history после override
r = c.get('/api/v1/users/me/targets/protein_target_g/history/')
arr = show("GET history (protein, after override)", r)
print(f"   entries: {len(arr or [])}")
for e in (arr or [])[:3]:
    print(f"   - src={e['source']:10s}  old={e['old_value']}  new={e['new_value']}  by={e.get('by_user')}")

# 2.5) POST reset
r = c.post('/api/v1/users/me/targets/protein_target_g/reset/')
data = show("POST reset/protein_target_g/", r)
p = (data or {}).get('profile') or {}
m = (p.get('targets_meta') or {}).get('protein_target_g') or {}
print(f"   protein val (after reset) = {p.get('protein_target_g')}")
print(f"   protein src               = {m.get('source')}  by={m.get('by_user')}")

# 2.6) bad field
r = c.get('/api/v1/users/me/targets/invalid_field/history/')
data = show("GET history (invalid field — ожидаем 400)", r)
print(f"   body: {json.dumps(data, ensure_ascii=False)[:200]}")

# 2.7) Family
r = c.get('/api/v1/family/')
data = show("GET /family/", r)
print(f"   name: {(data or {}).get('name')}")
member_id = None
for m in (data or {}).get('members', []):
    p = m.get('profile') or {}
    meta = p.get('targets_meta')
    print(f"   member id={m['id']} email={m.get('email')!r}  meta? {'YES' if meta else 'NO'}")
    if meta:
        print('     →', json.dumps({k: v.get('source') for k, v in meta.items()}, ensure_ascii=False))
    if m.get('email') == 'mg205ui_smoke@test.local':
        member_id = m['id']

if member_id:
    # 2.8) family history
    r = c.get(f'/api/v1/family/members/{member_id}/targets/calorie_target/history/')
    arr = show(f"GET family history (member={member_id}, calorie)", r)
    print(f"   entries: {len(arr or [])}")
    for e in (arr or [])[:3]:
        print(f"   - src={e['source']:10s}  new={e['new_value']}")

    # 2.9) family reset
    r = c.post(f'/api/v1/family/members/{member_id}/targets/protein_target_g/reset/')
    data = show(f"POST family reset (member={member_id}, protein)", r)
    p = (data or {}).get('profile') or {}
    meta = (p.get('targets_meta') or {}).get('protein_target_g') or {}
    print(f"   protein val = {p.get('protein_target_g')}")
    print(f"   protein src = {meta.get('source')}")

print()
print("=== ALL ASSERTIONS BELOW ===")

# Лёгкий self-check (warnings, not failures)
fails = []
def chk(cond, msg):
    if not cond: fails.append(msg)

# Ещё раз обновим состояние и проверим логику lock+reset
r = c.patch('/api/v1/users/me/',
            data=json.dumps({'profile': {'fat_target_g': '99.9'}}),
            content_type='application/json')
data = r.json()
fat_meta = ((data.get('profile') or {}).get('targets_meta') or {}).get('fat_target_g') or {}
chk(fat_meta.get('source') == 'user', f"after PATCH fat → src must be 'user', got {fat_meta.get('source')}")

r = c.post('/api/v1/users/me/targets/fat_target_g/reset/')
data = r.json()
fat_meta = ((data.get('profile') or {}).get('targets_meta') or {}).get('fat_target_g') or {}
chk(fat_meta.get('source') == 'auto', f"after RESET fat → src must be 'auto', got {fat_meta.get('source')}")

if fails:
    print("FAIL:")
    for m in fails: print("  -", m)
else:
    print("OK: all self-checks passed")
PYEOF

echo ""
echo "=== SMOKE v3 DONE @ $TS ==="
