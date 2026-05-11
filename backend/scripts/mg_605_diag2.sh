#!/usr/bin/env bash
# MG-605 diag part 2 (18-24): фикс heredoc + БД через python
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== 18. БД: фактическая структура diary_entries / water_logs / menu_items ==="
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.db import connection
cur = connection.cursor()
for tbl in ("diary_entries", "water_logs", "menu_items"):
    print(f"\n--- {tbl} ---")
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, [tbl])
    for row in cur.fetchall():
        print(f"  {row[0]:30s} {row[1]:25s} null={row[2]:5s} default={row[3]}")
    cur.execute("""
        SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s
    """, [tbl])
    print("  indexes:")
    for ix in cur.fetchall():
        print(f"    {ix[0]}: {ix[1]}")
PY
echo

echo "=== 19. Текущие тесты apps/diary ==="
$COMPOSE exec -T backend bash -c 'find apps/diary -name "test_*.py" 2>/dev/null | xargs -I{} sh -c "echo === {} ===; cat {}"'
echo

echo "=== 20. Прогон pytest на apps/diary (текущее состояние) ==="
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=no 2>&1 | tail -10
echo

echo "=== 21. showmigrations diary ==="
$COMPOSE exec -T backend python manage.py showmigrations diary 2>&1
echo

echo "=== 22. Циклические зависимости diary <-> menu ==="
$COMPOSE exec -T backend bash -c 'grep -rn "from apps.menu\|import apps.menu" apps/diary/ 2>/dev/null || echo "нет импортов из menu в diary"'
echo "---"
$COMPOSE exec -T backend bash -c 'grep -rn "from apps.diary\|import apps.diary" apps/menu/ 2>/dev/null || echo "нет импортов из diary в menu"'
echo

echo "=== 23. Тарифные ограничения для дневника ==="
$COMPOSE exec -T backend bash -c 'grep -rn -i "premium\|plan_code\|subscription" apps/diary/ 2>/dev/null | head -20 || echo "нет упоминаний"'
echo

echo "=== 24. Coverage apps/diary ==="
$COMPOSE exec -T backend bash -c '
  coverage run --source=apps/diary -m pytest apps/diary/ -q --tb=no 2>&1 | tail -3
  echo "---"
  coverage report --include="apps/diary/*" 2>&1
'
echo

echo "=== 25. apps/menu/views.py — полный MenuGenerateView (строки 126-200) ==="
$COMPOSE exec -T backend sed -n '126,200p' apps/menu/views.py
echo

echo "=== 26. apps/menu/generator.py — _get_calorie_target / _get_hard_exclude ==="
$COMPOSE exec -T backend grep -nA15 "_get_calorie_target\|_get_hard_exclude" apps/menu/generator.py | head -60
echo

echo "=== 27. apps/menu/generator.py — filters_used (что сохраняется в Menu.filters_used) ==="
$COMPOSE exec -T backend grep -nB2 -A5 "filters_used\|filters\[" apps/menu/views.py | head -40
echo

echo "=== DONE part 2 ==="
