#!/usr/bin/env bash
# MG-602 diag #3: запуск через manage.py shell (Django настроен)
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg602_diag3_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  MG-602 DIAG #3  ($TS)"
echo "=========================================="

PYCODE=$(cat <<'PYEOF'
print('--- [1] MenuItem fields ---')
from apps.menu.models import MenuItem
for f in MenuItem._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print('is_salad in fields:', any(f.name == 'is_salad' for f in MenuItem._meta.get_fields()))
print()

print('--- [2] User fields (allergies?) ---')
from apps.users.models import User
for f in User._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print('allergies in User fields:', any(f.name == 'allergies' for f in User._meta.get_fields()))
print('user_type field:', User._meta.get_field('user_type'))
ut = User._meta.get_field('user_type')
print('user_type choices:', getattr(ut, 'choices', None))
print()

print('--- [3] FamilyMember ---')
from apps.family.models import FamilyMember
for f in FamilyMember._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print('Role choices:', list(FamilyMember.Role.choices))
print()

print('--- [4] DeletedMenu ---')
from apps.menu.models import DeletedMenu
for f in DeletedMenu._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print()

print('--- [5] FridgeItem ---')
from apps.fridge.models import FridgeItem
for f in FridgeItem._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print()

print('--- [6] ShoppingItem / ShoppingList ---')
from apps.menu.models import ShoppingItem, ShoppingList
print('ShoppingList:')
for f in ShoppingList._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print(' ', (f.name, f.__class__.__name__))
print('ShoppingItem:')
for f in ShoppingItem._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print(' ', (f.name, f.__class__.__name__))
print()

print('--- [7] Subscription / Plan ---')
from apps.subscriptions.models import Subscription
for f in Subscription._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print('Status choices:', list(Subscription.Status.choices))
try:
    from apps.subscriptions.models import Plan
    print('Plan:')
    for f in Plan._meta.get_fields():
        if not f.is_relation or f.many_to_one:
            print(' ', (f.name, f.__class__.__name__))
except Exception as e:
    print('Plan import error:', e)
print()

print('--- [8] Recipe ---')
from apps.recipes.models import Recipe
print([f.name for f in Recipe._meta.get_fields() if not f.is_relation or f.many_to_one])
print()

print('--- [9] views.py source — MenuRestoreView (отступ строки 316) ---')
import inspect
from apps.menu import views
src = inspect.getsource(views.MenuRestoreView)
for i, line in enumerate(src.split('\n'), start=1):
    print(f'{i:3} | {line!r}')
PYEOF
)

echo
echo "$PYCODE" | $COMPOSE exec -T backend python manage.py shell

echo
echo "--- [10] grep is_salad по проекту ---"
grep -rn "is_salad" "$ROOT/backend/apps/" 2>/dev/null || echo "  (нет совпадений)"

echo
echo "--- [11] grep allergies по apps/users + apps/family ---"
grep -rnE "allergies" "$ROOT/backend/apps/users/" "$ROOT/backend/apps/family/" 2>/dev/null | head -30

echo
echo "=========================================="
echo "  MG-602 DIAG #3 DONE → $OUT"
echo "=========================================="
