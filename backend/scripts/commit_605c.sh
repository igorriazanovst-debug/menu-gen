#!/bin/bash
# MG-605.C коммит: Premium gate + ?member_id= + PATCH владельцем
# Расположение: /opt/menugen/backend/scripts/commit_605c.sh

set -eu
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"
cd "$PROJECT_DIR"

echo "=== git status ==="
git -C "$PROJECT_DIR" status --short

echo ""
echo "=== git add ==="
git -C "$PROJECT_DIR" add \
    backend/apps/subscriptions/permissions.py \
    backend/apps/diary/permissions.py \
    backend/apps/diary/views.py \
    backend/apps/diary/serializers.py \
    backend/apps/diary/tests/test_mg_605c_permissions.py \
    backend/apps/diary/tests/test_diary.py \
    backend/apps/diary/tests/test_mg_605b_planned_eaten.py \
    backend/scripts/

git -C "$PROJECT_DIR" status --short

echo ""
echo "=== git commit ==="
git -C "$PROJECT_DIR" commit -m "MG-605.C: Premium gate + member_id filter + PATCH владельцем

- apps/subscriptions/permissions.py: has_active_premium(family) + IsFamilyPremium
  Premium = подписка plan.code='premium', status IN ('active','trial'), expires_at>now()
- apps/diary/permissions.py: IsDiaryEntryOwner (PATCH/DELETE только владельцем)
- apps/diary/views.py:
  * IsFamilyPremium на всех diary views (включая stats и water)
  * ?member_id= в list/stats: HEAD видит всех в своей семье, MEMBER только себя
  * DiaryEntryDetailView → RetrieveUpdateDestroyAPIView (добавлен PATCH)
  * PATCH запрещает менять поле member
- apps/diary/serializers.py: validate() partial-friendly (учитывает instance)
- apps/diary/tests/test_mg_605c_permissions.py: 24 теста
  (Premium gate, ?member_id=, PATCH, DELETE, stats с ?member_id=)
- apps/diary/tests/test_diary.py + test_mg_605b_planned_eaten.py:
  Premium-подписка добавлена в setup-фикстуры

Регресс: 317 passed (menu + recipes + diary + family + subscriptions)"

echo ""
echo "=== Последние 3 коммита ==="
git -C "$PROJECT_DIR" log --oneline -3
