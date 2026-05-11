#!/usr/bin/env bash
# MG-605 diagnose: текущее состояние diary, menu (мульти-член), family
set -eu
ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=================================================================="
echo "=== MG-605 DIAG: diary + menu (multi-member) + family ==="
echo "=================================================================="
echo

echo "=== 1. apps/diary/models.py (текущее состояние) ==="
$COMPOSE exec -T backend cat apps/diary/models.py
echo

echo "=== 2. apps/diary/serializers.py ==="
$COMPOSE exec -T backend cat apps/diary/serializers.py
echo

echo "=== 3. apps/diary/views.py ==="
$COMPOSE exec -T backend cat apps/diary/views.py
echo

echo "=== 4. apps/diary/urls.py ==="
$COMPOSE exec -T backend cat apps/diary/urls.py
echo

echo "=== 5. apps/diary/migrations/ — список ==="
$COMPOSE exec -T backend ls -la apps/diary/migrations/
echo

echo "=== 6. apps/diary/tests/ — что есть? ==="
$COMPOSE exec -T backend bash -c 'ls -la apps/diary/tests/ 2>/dev/null || echo "НЕТ ПАПКИ tests/"'
echo

echo "=== 7. apps/diary/apps.py + __init__.py ==="
$COMPOSE exec -T backend bash -c 'cat apps/diary/apps.py 2>/dev/null; echo "---"; cat apps/diary/__init__.py 2>/dev/null'
echo

echo "=== 8. INSTALLED_APPS: есть ли apps.diary ==="
$COMPOSE exec -T backend bash -c 'grep -n "apps.diary\|diary" config/settings.py | head -20'
echo

echo "=== 9. Главный urls.py: подключен ли /diary/ ==="
$COMPOSE exec -T backend bash -c 'grep -n "diary\|api/v1" config/urls.py'
echo

echo "=== 10. apps/menu/models.py — MenuItem (для FK planned_menu_item) ==="
$COMPOSE exec -T backend cat apps/menu/models.py
echo

echo "=== 11. apps/menu/generator.py — head/start (для мульти-член) ==="
$COMPOSE exec -T backend sed -n '1,80p' apps/menu/generator.py
echo

echo "=== 12. apps/menu/generator.py — все вызовы _resolve_member / member_id ==="
$COMPOSE exec -T backend grep -nE "member|family|target_kcal|calories_target" apps/menu/generator.py | head -50
echo

echo "=== 13. apps/menu/serializers.py — GenerateMenuSerializer ==="
$COMPOSE exec -T backend cat apps/menu/serializers.py
echo

echo "=== 14. apps/menu/views.py — MenuGenerateView (передача в Generator) ==="
$COMPOSE exec -T backend grep -nA20 "class MenuGenerateView\|def post" apps/menu/views.py | head -80
echo

echo "=== 15. apps/family/models.py (FamilyMember поля: kcal, allergies) ==="
$COMPOSE exec -T backend cat apps/family/models.py
echo

echo "=== 16. apps/users/models.py — calorie_target, allergies, disliked_products ==="
$COMPOSE exec -T backend cat apps/users/models.py
echo

echo "=== 17. apps/family/migrations/ — список (для проверки полей в БД) ==="
$COMPOSE exec -T backend ls apps/family/migrations/
echo

echo "=== 18. БД: фактическая структура diary_entries ==="
$COMPOSE exec -T backend python manage.py dbshell <<'SQL' 2>/dev/null || $COMPOSE exec -T db psql -U menugen -d menugen <<'SQL'
\d diary_entries
\d water_logs
\d menu_items
SQL
echo

echo "=== 19. Текущие тесты apps/diary (если есть) ==="
$COMPOSE exec -T backend bash -c 'find apps/diary -name "test_*.py" 2>/dev/null | xargs -I{} sh -c "echo === {} ===; cat {}" 2>/dev/null || echo "тестов нет"'
echo

echo "=== 20. Прогон pytest на apps/diary (текущее состояние) ==="
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=no 2>&1 | tail -10
echo

echo "=== 21. Проверка существующих миграций (showmigrations diary) ==="
$COMPOSE exec -T backend python manage.py showmigrations diary 2>&1
echo

echo "=== 22. Совместимость: импорт MenuItem из apps.menu (циклические зависимости?) ==="
$COMPOSE exec -T backend bash -c 'grep -rn "from apps.menu\|import apps.menu" apps/diary/ 2>/dev/null || echo "нет импортов из menu в diary"'
echo
$COMPOSE exec -T backend bash -c 'grep -rn "from apps.diary\|import apps.diary" apps/menu/ 2>/dev/null || echo "нет импортов из diary в menu"'
echo

echo "=== 23. Тарифные ограничения: где проверяется план для дневника? ==="
$COMPOSE exec -T backend bash -c 'grep -rn "premium\|Premium\|plan_code\|diary" apps/diary/views.py 2>/dev/null | head -20'
echo

echo "=== 24. Coverage apps/diary текущий ==="
$COMPOSE exec -T backend bash -c '
  coverage run --source=apps/diary -m pytest apps/diary/ -q --tb=no 2>&1 | tail -3
  echo "---"
  coverage report --include="apps/diary/*" 2>&1
'
echo

echo "=================================================================="
echo "=== DONE MG-605 DIAG ==="
echo "=================================================================="
