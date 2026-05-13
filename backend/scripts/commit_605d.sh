#!/usr/bin/env bash
# MG-605.D commit
set -eu
ROOT="/opt/menugen"
cd "$ROOT"

echo "=== git status ==="
git status
echo

echo "=== git diff --stat ==="
git diff --stat
echo

echo "=== Добавляем файлы 605.D ==="
git add \
  backend/apps/diary/views.py \
  backend/apps/diary/serializers.py \
  backend/apps/diary/urls.py \
  backend/apps/diary/tests/test_diary.py \
  backend/apps/diary/tests/test_mg_605c_permissions.py \
  backend/apps/diary/tests/test_mg_605d_import.py \
  backend/apps/diary/tests/test_mg_605d_stats.py \
  backend/scripts/diag_605d.sh \
  backend/scripts/diag_605d_part2.sh \
  backend/scripts/diag_605d_stats_tests.sh \
  backend/scripts/apply_605d.sh \
  backend/scripts/regress_605d.sh \
  backend/scripts/regress_605d_live.sh

echo
echo "=== git status (после add) ==="
git status
echo

echo "=== Коммит ==="
git commit -m "MG-605.D: import-from-menu + stats план/факт

Новый эндпоинт:
- POST /api/v1/diary/import-from-menu/?menu_id=&date=&member_id=
  Импорт MenuItem'ов меню как плановых DiaryEntry на указанную дату.
  Идемпотентно через UNIQUE на planned_menu_item_id.
  HEAD импортирует за любого члена семьи через ?member_id=, MEMBER — только за себя.
  Импортируются позиции target-члена + общие (member IS NULL).
  Ответ: 200 {created, skipped, entries}.

Изменён формат GET /api/v1/diary/stats/ (BREAKING):
- было:  [{date, calories, proteins, fats, carbs}]
- стало: [{date, planned: {...}, actual: {...}, total: {...}}]

Логика:
- planned = planned_menu_item IS NOT NULL
- actual = is_eaten=True OR planned_menu_item IS NULL
  (вручную добавленное считается фактом сразу; плановое — только после галочки)
- total = actual (синоним для UI прогресс-бара)

Тесты:
- test_mg_605d_import.py: 9 тестов
- test_mg_605d_stats.py: 6 тестов
- адаптированы существующие stats-тесты под новый формат

Регресс: 383 passed (все apps/) за 4м25с.
Миграций не требуется (поля уже добавлены в 605.B)."

echo
echo "=== git log -1 ==="
git log -1 --stat
echo
echo "=== DONE. Для отправки в origin:  cd $ROOT && git push ==="
