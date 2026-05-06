#!/bin/bash
set -euo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
F="$ROOT/backend/apps/menu/serializers.py"
TS="$(date +%Y%m%d_%H%M%S)"
cp -v "$F" "/tmp/mg_304_v5_backup_${TS}_serializers.py"

echo
echo "=== [1] текущий serializers.py ==="
cat -n "$F"
echo

echo "=== [2] патч: warnings в MenuDetailSerializer.Meta.fields ==="
python3 - "$F" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

if "MG_304_V_serializers" in src:
    print("SKIP: уже пропатчен"); sys.exit(0)

# Ищем блок MenuDetailSerializer ... до следующего class или конца файла
m = re.search(r"(class\s+MenuDetailSerializer\b[^:]*:.+?)(?=\nclass\s|\Z)", src, re.DOTALL)
if not m:
    print("FATAL: MenuDetailSerializer не найден", file=sys.stderr); sys.exit(1)

cls = m.group(1)
# Ищем fields = (...) или fields = [...]
fm = re.search(r"fields\s*=\s*([\[(])([^\])]*)([\])])", cls)
if not fm:
    print("FATAL: Meta.fields не найден в MenuDetailSerializer", file=sys.stderr); sys.exit(1)

if "warnings" in fm.group(2):
    print("SKIP: 'warnings' уже в fields"); sys.exit(0)

inner = fm.group(2).rstrip().rstrip(",")
new_fields = f'{fm.group(1)}{inner}, "warnings"{fm.group(3)}  # MG_304_V_serializers'
new_cls = cls.replace(fm.group(0), new_fields)
src = src.replace(cls, new_cls, 1)
p.write_text(src, encoding="utf-8")
print("OK: warnings добавлен в MenuDetailSerializer.Meta.fields")
PYEOF

echo
echo "=== [3] verify ==="
grep -nE "warnings|MG_304_V_serializers|class MenuDetailSerializer|fields\s*=" "$F" | head -30

echo
echo "=== [4] compile + restart backend (чтобы Django подхватил изменения) ==="
docker compose -f "$COMPOSE" exec -T backend python -c "import py_compile; py_compile.compile('/app/apps/menu/serializers.py', doraise=True); print('compile OK')"
docker compose -f "$COMPOSE" restart backend >/dev/null
sleep 3
echo "backend restarted"

echo
echo "=== [5] HTTP smoke ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from datetime import date, timedelta
from django.conf import settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

allowed = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])
host = next((h for h in allowed if h and not h.startswith('.')), None) or 'localhost'

User = get_user_model()
u = User.objects.filter(email='admin@dev.local').first()
c = APIClient(SERVER_NAME=host); c.force_authenticate(user=u)
start = date.today() + timedelta(days=2)
resp = c.post('/api/v1/menu/generate/', {
    'start_date': start.isoformat(),
    'period_days': 2,
    'meal_plan_type': '3',
}, format='json')
print('status:', resp.status_code)
data = resp.json()
print('keys:', sorted(list(data.keys())))
print('warnings present:', 'warnings' in data, 'value:', data.get('warnings'))
print('items count:', len(data.get('items', [])))
items = data.get('items', [])
snack = [i for i in items if (i.get('meal_slot') or '').startswith('snack')]
print('snack items:', len(snack))
for s in snack[:5]:
    rec = s.get('recipe')
    rec_title = rec.get('title') if isinstance(rec, dict) else rec
    print('   slot=', s.get('meal_slot'), 'role=', s.get('component_role'), 'recipe=', rec_title)
"

echo "=========================================="
