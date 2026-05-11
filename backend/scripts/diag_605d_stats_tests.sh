#!/usr/bin/env bash
# MG-605.D mini-diag: stats-секции в существующих тестах, чтобы не сломать их
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== 1. test_diary.py — все вхождения stats / calories / proteins / DiaryStats ==="
$COMPOSE exec -T backend grep -nE "stats|calories|proteins|fats|carbs|diary-stats|DiaryStats" apps/diary/tests/test_diary.py || echo "  (не найдено)"
echo

echo "=== 2. test_diary.py — полный список классов и тестов ==="
$COMPOSE exec -T backend grep -nE "^(class |    def test_)" apps/diary/tests/test_diary.py
echo

echo "=== 3. test_diary.py — полный файл (если он короткий) ==="
$COMPOSE exec -T backend wc -l apps/diary/tests/test_diary.py
$COMPOSE exec -T backend cat apps/diary/tests/test_diary.py
echo

echo "=== 4. test_mg_605b_planned_eaten.py — все упоминания stats ==="
$COMPOSE exec -T backend grep -nE "stats|calories|proteins|diary-stats" apps/diary/tests/test_mg_605b_planned_eaten.py || echo "  (не найдено)"
echo

echo "=== 5. test_mg_605c_permissions.py — все упоминания stats ==="
$COMPOSE exec -T backend grep -nE "stats|calories|proteins|diary-stats" apps/diary/tests/test_mg_605c_permissions.py || echo "  (не найдено)"
echo

echo "=== 6. Где ещё в проекте используется diary-stats (фронт/мобила) ==="
$COMPOSE exec -T backend bash -c 'grep -rn "diary/stats\|diary-stats\|DiaryStats" --include="*.py" 2>/dev/null || echo "  (только в diary/)"'
echo

echo "=== DONE ==="
