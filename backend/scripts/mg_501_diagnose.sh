#!/usr/bin/env bash
# MG-501 diagnose: текущее состояние Recipe (модель, миграции, сериализаторы, фронт)
set -uo pipefail

BACKEND="/opt/menugen/backend"
WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
COMPOSE="/opt/menugen/docker-compose.yml"

hdr()   { echo; echo "=== $* ==="; }

hdr "0. Окружение"
[ -d "$BACKEND" ] && echo "  ✅ $BACKEND" || { echo "  ❌ $BACKEND"; exit 1; }
[ -d "$WEB" ]     && echo "  ✅ $WEB"     || { echo "  ❌ $WEB"; exit 1; }

hdr "1. apps/recipes/models.py — текущие поля Recipe"
grep -n "field\|Field\|class Recipe\|class Cooking\|class FoodGroup\|class ProteinType\|class GrainType\|cooking_method\|has_added_sugar\|oil_tsp\|serving_size_label" \
  "$BACKEND/apps/recipes/models.py" | head -80

hdr "2. apps/recipes/migrations — последние миграции"
ls -1 "$BACKEND/apps/recipes/migrations/" | grep -E "^[0-9]" | sort | tail -5

hdr "3. apps/recipes/serializers.py — поля сериализаторов"
grep -n "CLASSIFICATION_FIELDS\|food_group\|cooking_method\|has_added_sugar\|oil_tsp\|serving_size_label\|class.*Serializer" \
  "$BACKEND/apps/recipes/serializers.py" | head -40

hdr "4. web types/index.ts — текущие поля Recipe"
grep -nE "FoodGroup|ProteinType|GrainType|CookingMethod|cooking_method|has_added_sugar|oil_tsp|serving_size_label|export interface Recipe|^export type" \
  "$SRC/types/index.ts" | head -30

hdr "5. web RecipeEditModal.tsx — вкладка classification"
F="$SRC/components/recipes/RecipeEditModal.tsx"
echo "файл: $F"
[ -f "$F" ] && echo "  ✅ есть ($(wc -l < "$F") строк)" || { echo "  ❌ НЕТ"; exit 1; }
grep -nE "tab === 'classification'|cooking_method|has_added_sugar|oil_tsp|serving_size_label|FOOD_GROUP_OPTIONS|PROTEIN_TYPE_OPTIONS|GRAIN_TYPE_OPTIONS|SUITABLE_FOR_OPTIONS|isFattyFish|isRedMeat" \
  "$F" | head -30

hdr "6. БД: контейнер и текущая schema recipes"
CONT="$(docker compose -f "$COMPOSE" ps -q web 2>/dev/null | head -1)"
[ -z "$CONT" ] && CONT="$(docker compose -f "$COMPOSE" ps -q backend 2>/dev/null | head -1)"

if [ -n "$CONT" ]; then
  echo "  backend контейнер: $CONT"
  echo
  echo "[6.1] showmigrations recipes"
  docker exec "$CONT" python manage.py showmigrations recipes 2>/dev/null | sed 's/^/    /'
  echo
  echo "[6.2] описание таблицы recipes — есть ли уже наши колонки?"
  docker exec "$CONT" python manage.py dbshell -- -c "\d recipes" 2>/dev/null \
    | grep -iE "cooking_method|has_added_sugar|oil_tsp|serving_size_label" \
    | sed 's/^/    /' || echo "    (колонок ещё нет — ожидаемо)"
  echo
  echo "[6.3] количество рецептов"
  docker exec "$CONT" python manage.py shell -c "
from apps.recipes.models import Recipe
print(f'total: {Recipe.objects.count()}')" 2>/dev/null | sed 's/^/    /'
else
  echo "  ❌ backend контейнер не найден"
fi

hdr "7. tsc baseline (фронт)"
cd "$WEB"
if [ -d node_modules ]; then
  npx --no-install tsc --noEmit 2>&1 | tail -3 | sed 's/^/    /'
else
  echo "    node_modules нет — пропуск"
fi

hdr "Готово"
