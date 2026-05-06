#!/bin/bash
# MG-304 smoke v2: исправлено — все блоки через manage.py shell -c (Django settings гарантированно).
set -uo pipefail

ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"

echo "=========================================="
echo "  MG-304 SMOKE v2  $(date '+%F %T')"
echo "=========================================="

echo
echo "[1] pytest MG-304 + MG-301 (регресс)"
docker compose -f "$COMPOSE" exec -T backend pytest \
  apps/menu/tests/test_mg_301.py \
  apps/menu/tests/test_mg_304.py -q 2>&1 | tail -30

echo
echo "[2] e2e: реальная генерация для admin@dev.local"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from datetime import date
from apps.menu.generator import MenuGenerator
from apps.menu.portions import daily_target_grams, recipe_portion_grams
from apps.family.models import Family, FamilyMember

family = Family.objects.filter(members__user__email='admin@dev.local').first() or Family.objects.first()
print('family:', family.id, family.name)
members = list(FamilyMember.objects.filter(family=family).select_related('user__profile'))
print('members:', [(m.id, getattr(m.user, 'email', None), getattr(getattr(m.user, 'profile', None), 'birth_year', None)) for m in members])

start = date.today()
g = MenuGenerator(family=family, members=members, period_days=2, start_date=start, plan_code='free', filters={'meal_plan_type': '3'})
items = g.generate()

agg = {}
virt = 0
for it in items:
    if it.get('is_virtual'):
        virt += 1
    if it.get('component_role') in ('vegetable', 'fruit'):
        k = (it['member'].id, it['day_offset'])
        agg[k] = agg.get(k, 0.0) + recipe_portion_grams(it['recipe'])

print('items total:', len(items), 'virtual snacks:', virt)
print('warnings:', g.last_warnings)
for m in members:
    target = daily_target_grams(m, ref_date=start)
    for d in range(2):
        got = agg.get((m.id, d), 0.0)
        flag = 'OK' if got >= target - 0.01 else 'MISS'
        print(f'  member={m.id} day={d}: {got:.1f}/{target:.1f} g  {flag}')
"

echo
echo "[3] HTTP: POST /api/menu/generate/ (через manage.py shell -c)"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from datetime import date, timedelta
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.filter(email='admin@dev.local').first()
if not u:
    print('admin@dev.local not found — skip')
else:
    c = APIClient()
    c.force_authenticate(user=u)
    start = date.today() + timedelta(days=1)
    resp = c.post('/api/menu/generate/', {
        'start_date': start.isoformat(),
        'period_days': 2,
        'meal_plan_type': '3',
    }, format='json')
    print('status:', resp.status_code)
    if resp.status_code < 500:
        data = resp.json()
        if isinstance(data, dict):
            print('warnings field present:', 'warnings' in data)
            print('warnings:', data.get('warnings'))
            print('items count:', len(data.get('items', [])))
            print('keys:', sorted(list(data.keys())))
        else:
            print('not dict:', type(data), str(data)[:300])
    else:
        print('RAW:', resp.content[:500])
"

echo
echo "=========================================="
echo "  MG-304 SMOKE v2: DONE"
echo "=========================================="
