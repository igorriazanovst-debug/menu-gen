#!/usr/bin/env bash
# MG-604 commit + финальный coverage
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
cd "$ROOT"

echo "=========================================="
echo "  MG-604 COMMIT"
echo "=========================================="

echo
echo "--- git status ---"
git status --short

git add backend/apps/recipes/tests/conftest.py
git add backend/apps/recipes/tests/test_mg_604_permissions.py
git add backend/apps/recipes/tests/test_mg_604_views_country_apply.py
git add backend/apps/menu/tests/test_mg_604_exceptions.py
git add backend/apps/menu/tests/test_mg_604_portions.py

echo
echo "--- staged ---"
git status --short

git commit -m "MG-604: добивка coverage остатков

Tests:
- apps/recipes/tests/conftest.py — общие фикстуры
  (client, plain_user, author, admin, recipe)
- apps/recipes/tests/test_mg_604_permissions.py — 8 тестов
  IsAuthorOrAdmin (safe/admin/author/other),
  IsRecipeAuthorRole (safe/author/admin/plain)
- apps/recipes/tests/test_mg_604_views_country_apply.py — 8 тестов
  RecipeCountryListView (empty/distinct-sorted/unpublished/empty-country/strip),
  RecipeAuthorApplyView (success/duplicate-400/unauthenticated)
- apps/menu/tests/test_mg_604_exceptions.py — 8 тестов
  MenuGeneratorError.to_response, EmptyRolePoolError (msg/member/hint/unknown/details)
- apps/menu/tests/test_mg_604_portions.py — 28 тестов
  _age_multiplier (negative/None/parametrize 11 диапазонов),
  _member_age (no-profile/no-birth/exception/normal),
  daily_target_grams, recipe_portion_grams
  (nutrition.weight в разных формах, exception в обоих try-блоках, fallback)

Coverage:
- apps/recipes/permissions.py: 77% → 100%
- apps/recipes/views.py:       91% → 100%
- apps/menu/exceptions.py:     93% → 100%
- apps/menu/portions.py:       88% → 100%
- TOTAL: 95% → 96%+
- Тестов: 188 → 241"

echo
echo "--- последний коммит ---"
git log -1 --oneline

echo
echo "=========================================="
echo "  FINAL COVERAGE REPORT"
echo "=========================================="
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing
'

echo
echo "=========================================="
echo "  MG-604 COMMIT DONE"
echo "=========================================="
