#!/usr/bin/env bash
# MG-502/503 diagnose: смотрим текущий generator.py — особенно _WeeklyTracker, _pick_for_role,
# сигнатуру вызова, как сохраняются warnings, какие meal_slots используются.
set -uo pipefail

BACKEND="/opt/menugen/backend"
F_GEN="$BACKEND/apps/menu/generator.py"
F_PORT="$BACKEND/apps/menu/portions.py"
COMPOSE="/opt/menugen/docker-compose.yml"

hdr() { echo; echo "=== $* ==="; }

[ -f "$F_GEN" ] || { echo "❌ нет $F_GEN"; exit 1; }

hdr "1. Длина и маркеры в generator.py"
echo "  $(wc -l < "$F_GEN") строк"
grep -nE "MG_30[0-9]_V_|MG_50[0-9]_V_" "$F_GEN" | head -20

hdr "2. Все top-level constants"
grep -nE "^[A-Z_]+ *=" "$F_GEN" | head -25

hdr "3. _WeeklyTracker — поля _daily / _weekly / методы"
awk '/^class _WeeklyTracker/,/^class [A-Z]|^[A-Z_]+ =/' "$F_GEN" | head -90

hdr "4. _pick_for_role — сигнатура и тело"
awk '/def _pick_for_role/,/^    def [a-z_]/' "$F_GEN" | head -120

hdr "5. где вызывается _pick_for_role (передаём meal_type)"
grep -n "_pick_for_role" "$F_GEN"

hdr "6. как сохраняются warnings (поиск warnings, _collect_*_warnings)"
grep -nE "warnings|_collect_.*_warnings|last_warnings|self\.warnings" "$F_GEN" | head -30

hdr "7. portions.py: что есть на стороне портций"
[ -f "$F_PORT" ] && grep -nE "^def |^[A-Z_]+ *=" "$F_PORT" || echo "  нет файла"

hdr "8. MEAL_PLAN_3 / MEAL_PLAN_5 / MEAL_TYPE_DB"
grep -nE "MEAL_PLAN_3|MEAL_PLAN_5|MEAL_TYPE_DB|MEAL_COMPONENTS" "$F_GEN" | head -20

hdr "9. БД smoke: распределение oil_tsp / has_added_sugar в текущих рецептах"
CONT="$(docker compose -f "$COMPOSE" ps -q web 2>/dev/null | head -1)"
[ -z "$CONT" ] && CONT="$(docker compose -f "$COMPOSE" ps -q backend 2>/dev/null | head -1)"
if [ -n "$CONT" ]; then
  docker exec "$CONT" python manage.py shell -c "
from apps.recipes.models import Recipe
qs = Recipe.objects.all()
print(f'total: {qs.count()}')
print(f'has_added_sugar=True:           {qs.filter(has_added_sugar=True).count()}')
print(f'oil_tsp__isnull=False:          {qs.filter(oil_tsp__isnull=False).count()}')
print(f'oil_tsp > 0.5 (heavy):          {qs.filter(oil_tsp__gt=0.5).count()}')
print(f'cooking_method__isnull=False:   {qs.exclude(cooking_method__isnull=True).count()}')
print(f'serving_size_label__isnull=False: {qs.exclude(serving_size_label__isnull=True).count()}')
" 2>&1 | sed 's/^/    /'
else
  echo "  ❌ контейнер backend не найден"
fi

hdr "10. количество тестов apps/menu/"
ls "$BACKEND/apps/menu/tests/" | grep -E "^test_" | sed 's/^/    /'

hdr "Готово"
