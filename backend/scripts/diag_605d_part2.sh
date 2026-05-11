#!/usr/bin/env bash
# MG-605.D diagnose part 2: добиваем пункты 6-13 через manage.py shell
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "================================================================"
echo "  MG-605.D DIAGNOSE PART 2"
echo "================================================================"
echo

echo "=== 6. MenuItem — поля и константы ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
import inspect
from apps.menu.models import MenuItem
print(inspect.getsource(MenuItem))
print('--- fields summary ---')
for f in MenuItem._meta.get_fields():
    if not f.is_relation or f.many_to_one:
        print((f.name, f.__class__.__name__, getattr(f, 'null', None)))
PY
echo

echo "=== 7. БД: diary_entries структура ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.db import connection
cur = connection.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'diary_entries'
    ORDER BY ordinal_position
""")
print("--- diary_entries columns ---")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]:25s} null={row[2]:5s} default={row[3]}")
cur.execute("""
    SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'diary_entries'
""")
print("--- diary_entries indexes ---")
for ix in cur.fetchall():
    print(f"  {ix[0]}: {ix[1]}")
PY
echo

echo "=== 8. БД: menu_items структура ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.db import connection
cur = connection.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'menu_items'
    ORDER BY ordinal_position
""")
print("--- menu_items columns ---")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]:25s} null={row[2]:5s} default={row[3]}")
PY
echo

echo "=== 9. Текущие тесты apps/diary ==="
$COMPOSE exec -T backend bash -c 'find apps/diary -name "test_*.py" | sort'
echo

echo "=== 10. Прогон тестов apps/diary ==="
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=no 2>&1 | tail -10
echo

echo "=== 11. Миграции diary ==="
$COMPOSE exec -T backend python manage.py showmigrations diary 2>&1
echo

echo "=== 12. MenuItemSerializer (что вернётся в ответе entries) ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
import inspect
from apps.menu import serializers as s
for name in ['MenuItemSerializer']:
    obj = getattr(s, name, None)
    if obj:
        print(f'--- {name} ---')
        print(inspect.getsource(obj))
PY
echo

echo "=== 13. Полный регресс (sanity) ==="
$COMPOSE exec -T backend pytest apps/menu/ apps/recipes/ apps/diary/ apps/family/ apps/subscriptions/ -q --tb=no 2>&1 | tail -5
echo

echo "================================================================"
echo "  MG-605.D DIAGNOSE PART 2 DONE"
echo "================================================================"
