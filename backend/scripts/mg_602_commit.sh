#!/usr/bin/env bash
# MG-602 commit: закоммитить bugfix + новые тесты
set -eu

ROOT="/opt/menugen"
cd "$ROOT"

echo "=========================================="
echo "  MG-602 COMMIT"
echo "=========================================="

# Удалим backup'ы views.py
rm -f backend/apps/menu/views.py.bak.*

echo
echo "--- git status ---"
git status --short

echo
echo "--- git diff stat ---"
git diff --stat
echo
git diff --stat --cached

echo
echo "--- staging ---"
git add backend/apps/menu/views.py
git add backend/apps/menu/tests/test_mg_602_views.py

echo
echo "--- staged ---"
git status --short

echo
echo "--- commit ---"
git commit -m "MG-602: views.py coverage 67% → 100%

Bugfixes:
- _can_edit_menu: удалено обращение к m.can_edit_menu
  (поле удалено миграцией family/0004_remove_familymember_can_edit_menu)
- _menu_snapshot: добавлены meal_slot, component_role, is_cheat_meal
  (для корректного восстановления через MenuRestoreView)
- MenuRestoreView: убрана сломанная строка is_salad=item.get(...)
  (поле удалено миграцией menu/0006_component_role)
- _recipe_calories: расширен except до AttributeError
  (для случая nutrition['calories'] не dict)

Tests: apps/menu/tests/test_mg_602_views.py — 53 теста
- helpers: _can_edit_menu, _can_delete_menu, _check_allergens,
  _recipe_calories, _collect_allergens, _menu_snapshot
- views: MenuGenerate (404, фильтры), MenuList/Detail (404),
  MenuDelete (4 ветви), DeletedMenuList/Restore (5 кейсов),
  MenuItemSwap (8 кейсов: 404/403/food_group/calorie/allergen),
  MenuArchive, Shopping (8 кейсов)

Coverage:
- apps/menu/views.py: 67% → 100%
- TOTAL: 85% → 94%
- Тестов: 114 → 167"

echo
echo "--- последний коммит ---"
git log -1 --stat

echo
echo "=========================================="
echo "  MG-602 COMMIT DONE"
echo "=========================================="
