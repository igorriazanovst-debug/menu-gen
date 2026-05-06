#!/bin/bash
# MG-304 smoke v3: HTTP-блок c явным Host из ALLOWED_HOSTS.
set -uo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"

echo "=========================================="
echo "  MG-304 SMOKE v3 (HTTP only)  $(date '+%F %T')"
echo "=========================================="

echo
echo "[3] HTTP: POST /api/menu/generate/ — берём первый ALLOWED_HOSTS"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from datetime import date, timedelta
from django.conf import settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

allowed = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])
host = next((h for h in allowed if h and not h.startswith('.')), None) or 'localhost'
print('ALLOWED_HOSTS:', allowed, '-> using:', host)

User = get_user_model()
u = User.objects.filter(email='admin@dev.local').first()
if not u:
    print('admin@dev.local not found — skip'); raise SystemExit(0)

c = APIClient(SERVER_NAME=host)
c.force_authenticate(user=u)
start = date.today() + timedelta(days=1)
resp = c.post('/api/menu/generate/', {
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
    else:
        print('not dict:', type(data))
else:
    print('Content-Type:', ctype)
    print('RAW:', resp.content[:600])
"

echo
echo "=========================================="
echo "  SMOKE v3: DONE"
echo "=========================================="
