#!/usr/bin/env bash
# MG-602 diag #4: финальные проверки перед патчем
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg602_diag4_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  MG-602 DIAG #4  ($TS)"
echo "=========================================="

PYCODE=$(cat <<'PYEOF'
print('--- [1] FamilyMember: проверка can_edit_menu (поле или property) ---')
from apps.family.models import FamilyMember
all_attrs = [a for a in dir(FamilyMember) if 'edit' in a.lower() or 'can' in a.lower()]
print('attrs containing edit/can:', all_attrs)
all_field_names = [f.name for f in FamilyMember._meta.get_fields()]
print('all field names:', all_field_names)
print('can_edit_menu в полях:', 'can_edit_menu' in all_field_names)
try:
    print('class attr can_edit_menu:', getattr(FamilyMember, 'can_edit_menu', '<not found>'))
except Exception as e:
    print('error:', e)
print()

print('--- [2] _menu_snapshot: что сохраняется ---')
import inspect
from apps.menu import views
src = inspect.getsource(views._menu_snapshot)
print(src)
print()

print('--- [3] миграции menu: финальное состояние is_salad ---')
import os
mig_dir = os.path.join('apps', 'menu', 'migrations')
for f in sorted(os.listdir(mig_dir)):
    if f.endswith('.py') and not f.startswith('__'):
        path = os.path.join(mig_dir, f)
        with open(path) as fh:
            content = fh.read()
        if 'is_salad' in content:
            # ищем тип операции
            import re
            ops = re.findall(r'(AddField|RemoveField|AlterField).*?is_salad', content, re.S)
            print(f'{f}: ops={ops}')

print()
print('--- [4] Текущая структура DB (taken from migrations state) ---')
from django.db.migrations.loader import MigrationLoader
from django.db import connection
loader = MigrationLoader(connection)
state = loader.project_state()
mi_state = state.models.get(('menu', 'menuitem'))
if mi_state:
    print('menuitem fields in migration state:')
    for name, f in mi_state.fields.items():
        print(' ', name, type(f).__name__)
PYEOF
)

echo "$PYCODE" | $COMPOSE exec -T backend python manage.py shell

echo
echo "--- [5] grep can_edit_menu по проекту ---"
grep -rn "can_edit_menu" "$ROOT/backend/apps/" 2>/dev/null

echo
echo "--- [6] проверим все миграции menu по порядку (имена) ---"
ls -1 "$ROOT/backend/apps/menu/migrations/" | grep -E '^[0-9]'

echo
echo "=========================================="
echo "  MG-602 DIAG #4 DONE → $OUT"
echo "=========================================="
