#!/bin/bash
# Диагностика перед патчем MG-605.C
# Расположение: /opt/menugen/backend/scripts/diag_605c.sh
# Запуск:
#   bash /opt/menugen/backend/scripts/diag_605c.sh 2>&1 | tee /tmp/diag_605c.log

set -u
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"
cd "$PROJECT_DIR"

echo "===================================================================="
echo "DIAG-605.C — состояние перед патчем"
echo "===================================================================="

echo ""
echo "=== 1) Текущий бранч / коммит ==="
git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD
git -C "$PROJECT_DIR" log --oneline -5

echo ""
echo "=== 2) apps/diary/views.py — полный листинг ==="
docker compose exec -T backend cat apps/diary/views.py

echo ""
echo "=== 3) apps/diary/urls.py — полный листинг ==="
docker compose exec -T backend cat apps/diary/urls.py

echo ""
echo "=== 4) apps/diary/serializers.py — полный листинг ==="
docker compose exec -T backend cat apps/diary/serializers.py

echo ""
echo "=== 5) apps/diary/models.py — полный листинг ==="
docker compose exec -T backend cat apps/diary/models.py

echo ""
echo "=== 6) Существующие тесты diary (список файлов) ==="
docker compose exec -T backend ls -la apps/diary/tests/

echo ""
echo "=== 7) FamilyMember — какие роли есть в коде ==="
docker compose exec -T backend grep -nE "role|Role|ROLE|admin|head|HEAD|ADMIN" apps/family/models.py | head -40

echo ""
echo "=== 8) Premium tier — как определяется в коде ==="
docker compose exec -T backend bash -lc "grep -rnE 'is_premium|premium|tier|Tier|TIER' apps/ --include='*.py' | grep -v migrations | grep -v test | head -40"

echo ""
echo "=== 9) Premium gate где-нибудь используется? ==="
docker compose exec -T backend bash -lc "grep -rnE 'IsPremium|premium_required|HasPremium' apps/ --include='*.py' | head -20"

echo ""
echo "=== 10) Текущая модель пользователя — поля подписки ==="
docker compose exec -T backend bash -lc "grep -nE 'tier|subscription|premium|plan|Plan' apps/users/models.py apps/billing/models.py apps/subscriptions/models.py 2>/dev/null | head -30"

echo ""
echo "=== 11) Структура apps/ ==="
docker compose exec -T backend ls apps/

echo ""
echo "=== 12) Все permissions классы в проекте ==="
docker compose exec -T backend bash -lc "grep -rnE 'class.*Permission.*BasePermission|class.*Permission.*permissions\.' apps/ --include='*.py' | head -30"

echo ""
echo "=== 13) Существующие PATCH endpoints (для шаблона) ==="
docker compose exec -T backend bash -lc "grep -rnE 'RetrieveUpdate|UpdateAPIView|partial_update|def patch' apps/ --include='*.py' | head -20"

echo ""
echo "=== 14) Кол-во записей в diary_entries (продовая БД) ==="
docker compose exec -T db psql -U menugen_user -d menugen -c "SELECT COUNT(*) AS total, COUNT(planned_menu_item_id) AS with_plan, COUNT(*) FILTER (WHERE is_eaten) AS eaten FROM diary_entries;"

echo ""
echo "=== 15) Регресс — текущее число тестов diary ==="
docker compose exec -T backend pytest apps/diary/ -q --tb=no 2>&1 | tail -10

echo ""
echo "===================================================================="
echo "DIAG-605.C — конец"
echo "===================================================================="
