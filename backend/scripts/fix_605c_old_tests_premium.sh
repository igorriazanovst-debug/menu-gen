#!/bin/bash
# MG-605.C: фикс старых тестов diary — добавить Premium-подписку в setup-фикстуру
# Расположение: /opt/menugen/backend/scripts/fix_605c_old_tests_premium.sh

set -eu
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"

python3 <<'PYEOF'
"""
Точечный фикс двух файлов:
- apps/diary/tests/test_diary.py
- apps/diary/tests/test_mg_605b_planned_eaten.py

В обоих — фикстура `setup`. Сразу после создания `FamilyMember`
вставляем создание активной Premium-подписки.
"""
from pathlib import Path

PREMIUM_BLOCK_AFTER_MEMBER = '''    # MG-605.C: активная Premium-подписка, требуется новым gate
    from datetime import timedelta as _td
    from decimal import Decimal as _D
    from django.utils import timezone as _tz
    from apps.subscriptions.models import Subscription as _Sub, SubscriptionPlan as _Plan
    _plan, _ = _Plan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": _D("0")},
    )
    _Sub.objects.create(
        family=family,
        plan=_plan,
        status=_Sub.Status.ACTIVE,
        started_at=_tz.now() - _td(days=1),
        expires_at=_tz.now() + _td(days=30),
    )
'''

TARGETS = [
    ("/opt/menugen/backend/apps/diary/tests/test_diary.py",
     "    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)\n"),
    ("/opt/menugen/backend/apps/diary/tests/test_mg_605b_planned_eaten.py",
     "    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)\n"),
]

for path, anchor in TARGETS:
    p = Path(path)
    src = p.read_text()
    if "# MG-605.C: активная Premium-подписка" in src:
        print(f"SKIP (уже пропатчен): {path}")
        continue
    if anchor not in src:
        print(f"!! не найден якорь в {path}")
        continue
    new = src.replace(anchor, anchor + PREMIUM_BLOCK_AFTER_MEMBER, 1)
    p.write_text(new)
    print(f"OK: пропатчен {path}")
PYEOF

echo ""
echo "=== Проверка вставок ==="
grep -n "MG-605.C: активная Premium" \
    /opt/menugen/backend/apps/diary/tests/test_diary.py \
    /opt/menugen/backend/apps/diary/tests/test_mg_605b_planned_eaten.py

echo ""
echo "=== Чистка тест-БД ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='test_menugen' AND pid <> pg_backend_pid();" || true
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres -c "DROP DATABASE IF EXISTS test_menugen;" || true

echo ""
echo "=== Полный регресс diary ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend \
    pytest apps/diary/ -v --tb=short
