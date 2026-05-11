#!/usr/bin/env bash
# MG-605.D diagnose: import-from-menu + stats план/факт
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "================================================================"
echo "  MG-605.D DIAGNOSE"
echo "================================================================"
echo

echo "=== 1. apps/diary/views.py — полный файл ==="
$COMPOSE exec -T backend cat apps/diary/views.py
echo

echo "=== 2. apps/diary/serializers.py — полный файл ==="
$COMPOSE exec -T backend cat apps/diary/serializers.py
echo

echo "=== 3. apps/diary/models.py — полный файл ==="
$COMPOSE exec -T backend cat apps/diary/models.py
echo

echo "=== 4. apps/diary/urls.py — полный файл ==="
$COMPOSE exec -T backend cat apps/diary/urls.py
echo

echo "=== 5. apps/diary/permissions.py — полный файл ==="
$COMPOSE exec -T backend cat apps/diary/permissions.py
echo

echo "=== 6. apps/menu/models.py — только MenuItem (для импорта) ==="
$COMPOSE exec -T backend python -c "
import inspect
from apps.menu.models import MenuItem
print(inspect.getsource(MenuItem))
print('---')
fields = [(f.name, f.__class__.__name__, getattr(f, 'null', None), getattr(f, 'blank', None)) for f in MenuItem._meta.get_fields() if not f.is_relation or f.many_to_one]
for f in fields:
    print(f)
"
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
print("--- diary_entries ---")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]:25s} null={row[2]:5s} default={row[3]}")
cur.execute("""
    SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'diary_entries'
""")
print("indexes:")
for ix in cur.fetchall():
    print(f"  {ix[0]}: {ix[1]}")
PY
echo

echo "=== 8. БД: menu_items структура (для импорта) ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.db import connection
cur = connection.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'menu_items'
    ORDER BY ordinal_position
""")
print("--- menu_items ---")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]:25s} null={row[2]:5s} default={row[3]}")
PY
echo

echo "=== 9. Текущие тесты apps/diary (имена файлов) ==="
$COMPOSE exec -T backend bash -c 'find apps/diary -name "test_*.py" | sort'
echo

echo "=== 10. Прогон ВСЕХ тестов apps/diary (квалификация) ==="
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=no 2>&1 | tail -10
echo

echo "=== 11. Миграции diary ==="
$COMPOSE exec -T backend python manage.py showmigrations diary 2>&1
echo

echo "=== 12. apps/menu/serializers.py — MenuItemSerializer (если нужны поля для ответа) ==="
$COMPOSE exec -T backend python -c "
import inspect
from apps.menu import serializers as s
for name in dir(s):
    obj = getattr(s, name)
    if 'MenuItem' in name and inspect.isclass(obj):
        print(f'--- {name} ---')
        print(inspect.getsource(obj))
"
echo

echo "=== 13. Полный регресс (sanity) ==="
$COMPOSE exec -T backend pytest apps/menu/ apps/recipes/ apps/diary/ apps/family/ apps/subscriptions/ -q --tb=no 2>&1 | tail -5
echo

echo "================================================================"
echo "  MG-605.D DIAGNOSE DONE"
echo "================================================================"
