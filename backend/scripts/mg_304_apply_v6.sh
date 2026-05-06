#!/bin/bash
set -euo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
F="$ROOT/backend/apps/menu/serializers.py"

echo "=== восстанавливаю из последнего v5-бэкапа ==="
LAST=$(ls -1t /tmp/mg_304_v5_backup_*_serializers.py 2>/dev/null | head -1)
[ -n "$LAST" ] || { echo "FATAL: бэкап не найден"; exit 1; }
echo "from: $LAST"
cp -v "$LAST" "$F"

echo
echo "=== патчу через line-based замену (без regex по многострочным скобкам) ==="
python3 - "$F" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").splitlines()

# Ищем класс MenuDetailSerializer и в его блоке Meta строку с "items",
# заменяем "items", -> "items", "warnings",
in_class = False
in_meta = False
class_indent = None
patched = False
for i, ln in enumerate(lines):
    if ln.startswith("class MenuDetailSerializer"):
        in_class = True
        in_meta = False
        continue
    if in_class and ln.lstrip().startswith("class Meta"):
        in_meta = True
        continue
    if in_class and ln.startswith("class ") and "MenuDetailSerializer" not in ln:
        in_class = False
        in_meta = False
    if in_class and in_meta:
        # ищем строку с "items" в кортеже fields
        stripped = ln.strip()
        if stripped == '"items",' and "warnings" not in ln:
            indent = ln[:len(ln) - len(ln.lstrip())]
            lines[i] = ln.rstrip(",") + ',\n' + indent + '"warnings",  # MG_304_V_serializers'
            patched = True
            break
        if stripped == '"items"' and "warnings" not in ln:
            # последний элемент без запятой — добавим
            indent = ln[:len(ln) - len(ln.lstrip())]
            lines[i] = ln + ',\n' + indent + '"warnings",  # MG_304_V_serializers'
            patched = True
            break

if not patched:
    print("FATAL: строка с \"items\" в MenuDetailSerializer.Meta.fields не найдена", file=sys.stderr)
    sys.exit(1)

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("OK: warnings вставлен после items")
PYEOF

echo
echo "=== verify ==="
sed -n '40,60p' "$F"

echo
echo "=== compile ==="
docker compose -f "$COMPOSE" exec -T backend python -c "import py_compile; py_compile.compile('/app/apps/menu/serializers.py', doraise=True); print('compile OK')"

echo
echo "=== restart backend ==="
docker compose -f "$COMPOSE" restart backend >/dev/null
sleep 3

echo
echo "=== HTTP smoke ==="
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
start = date.today() + timedelta(days=3)
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
