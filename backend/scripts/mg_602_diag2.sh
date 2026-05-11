#!/usr/bin/env bash
# MG-602 diag #2: точечные проверки перед патчем
# 1) Поле is_salad в MenuItem (есть/нет, тип)
# 2) Поле allergies в User (есть/нет, тип)
# 3) Проверка работоспособности MenuRestoreView (можно ли вызвать без падения)
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg602_diag2_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  MG-602 DIAG #2  ($TS)"
echo "=========================================="

echo
echo "--- [1] MenuItem: все поля и наличие is_salad ---"
$COMPOSE exec -T backend python -c "
from apps.menu.models import MenuItem
fields = [(f.name, f.__class__.__name__, getattr(f, 'null', None)) for f in MenuItem._meta.get_fields() if not f.is_relation or f.many_to_one]
for f in fields:
    print(f)
print()
print('is_salad in fields:', any(f[0] == 'is_salad' for f in fields))
"

echo
echo "--- [2] User: поле allergies ---"
$COMPOSE exec -T backend python -c "
from apps.users.models import User
fields = [(f.name, f.__class__.__name__, getattr(f, 'null', None)) for f in User._meta.get_fields() if not f.is_relation or f.many_to_one]
for f in fields:
    print(f)
print()
print('allergies in fields:', any(f[0] == 'allergies' for f in fields))
"

echo
echo "--- [3] grep is_salad по проекту ---"
grep -rn "is_salad" "$ROOT/backend/apps/" 2>/dev/null || echo "  (нет совпадений)"

echo
echo "--- [4] grep allergies по apps/users + apps/family ---"
grep -rnE "allergies" "$ROOT/backend/apps/users/" "$ROOT/backend/apps/family/" 2>/dev/null | head -30

echo
echo "--- [5] FamilyMember: поля can_edit_menu, role ---"
$COMPOSE exec -T backend python -c "
from apps.family.models import FamilyMember
fields = [f.name for f in FamilyMember._meta.get_fields()]
print('fields:', fields)
print('Role choices:', list(FamilyMember.Role.choices) if hasattr(FamilyMember, 'Role') else 'no Role enum')
"

echo
echo "--- [6] User.user_type — какие значения ---"
$COMPOSE exec -T backend python -c "
from apps.users.models import User
print('user_type field:', User._meta.get_field('user_type'))
ut = User._meta.get_field('user_type')
print('choices:', getattr(ut, 'choices', None))
"

echo
echo "--- [7] DeletedMenu: поля, особенно deleted_by_id ---"
$COMPOSE exec -T backend python -c "
from apps.menu.models import DeletedMenu
fields = [(f.name, f.__class__.__name__) for f in DeletedMenu._meta.get_fields() if not f.is_relation or f.many_to_one]
for f in fields:
    print(f)
"

echo
echo "--- [8] FridgeItem: поля ---"
$COMPOSE exec -T backend python -c "
from apps.fridge.models import FridgeItem
fields = [(f.name, f.__class__.__name__) for f in FridgeItem._meta.get_fields() if not f.is_relation or f.many_to_one]
for f in fields:
    print(f)
"

echo
echo "--- [9] ShoppingItem / ShoppingList: поля ---"
$COMPOSE exec -T backend python -c "
from apps.menu.models import ShoppingItem, ShoppingList
print('--- ShoppingList ---')
for f in ShoppingList._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
print('--- ShoppingItem ---')
for f in ShoppingItem._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__))
"

echo
echo "--- [10] Subscription / Plan: поле code ---"
$COMPOSE exec -T backend python -c "
from apps.subscriptions.models import Subscription
fields = [(f.name, f.__class__.__name__) for f in Subscription._meta.get_fields() if not f.is_relation or f.many_to_one]
print('--- Subscription ---')
for f in fields:
    print(f)
print('Status choices:', list(Subscription.Status.choices))
print()
try:
    from apps.subscriptions.models import Plan
    print('--- Plan ---')
    for f in Plan._meta.get_fields():
        if not f.is_relation or f.many_to_one:
            print((f.name, f.__class__.__name__))
except Exception as e:
    print('Plan import error:', e)
"

echo
echo "--- [11] Recipe: проверка наличия country, food_group в фикстурах ---"
$COMPOSE exec -T backend python -c "
from apps.recipes.models import Recipe
fields = [f.name for f in Recipe._meta.get_fields() if not f.is_relation or f.many_to_one]
print('Recipe fields:', fields)
"

echo
echo "--- [12] Тест MenuRestoreView вживую (минимальный smoke) ---"
$COMPOSE exec -T backend python -c "
import django
django.setup() if not getattr(django, '_setup_done', False) else None
from apps.menu.models import DeletedMenu, MenuItem
# проверим, что код views импортируется без синтаксической ошибки
from apps.menu import views
print('views import OK')
# смотрим, что в строке 316 — реальный отступ
import inspect
src = inspect.getsource(views.MenuRestoreView)
for i, line in enumerate(src.split('\n')[40:60], start=41):
    print(f'{i:3} | {line}')
"

echo
echo "=========================================="
echo "  MG-602 DIAG #2 DONE → $OUT"
echo "=========================================="
