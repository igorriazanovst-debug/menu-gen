#!/bin/bash
set -uo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"

echo "=========================================="
echo "  MG-304 SMOKE v4 (HTTP)  $(date '+%F %T')"
echo "=========================================="

docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from datetime import date, timedelta
from django.conf import settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

allowed = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])
host = next((h for h in allowed if h and not h.startswith('.')), None) or 'localhost'

User = get_user_model()
u = User.objects.filter(email='admin@dev.local').first()
if not u:
    print('admin@dev.local not found — skip'); raise SystemExit(0)

c = APIClient(SERVER_NAME=host)
c.force_authenticate(user=u)
start = date.today() + timedelta(days=1)
resp = c.post('/api/v1/menu/generate/', {
    'start_date': start.isoformat(),
    'period_days': 2,
    'meal_plan_type': '3',
}, format='json')
print('status:', resp.status_code)
ctype = resp.get('Content-Type', '')
if 'application/json' in ctype:
    data = resp.json()
    if isinstance(data, dict):
        print('warnings field present:', 'warnings' in data)
        print('warnings value:', data.get('warnings'))
        print('items count:', len(data.get('items', [])))
        print('keys:', sorted(list(data.keys())))
        # сводка по виртуальным snack
        items = data.get('items', [])
        snacks = [i for i in items if (i.get('meal_slot') or '').startswith('snack')]
        print('snack items:', len(snacks))
        for s in snacks[:6]:
            print('   slot=', s.get('meal_slot'), 'role=', s.get('component_role'),
                  'recipe=', (s.get('recipe') or {}).get('title') if isinstance(s.get('recipe'), dict) else s.get('recipe'))
    else:
        print('not dict:', type(data))
else:
    print('Content-Type:', ctype)
    print('RAW first 500:', resp.content[:500])
"

echo "=========================================="
