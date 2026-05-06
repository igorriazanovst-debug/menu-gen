#!/bin/bash
# MG-304 — досмотр generator.py и views.py перед apply
set -uo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"

echo "=========================================="
echo "  MG-304 DIAGNOSE-2  $(date '+%F %T')"
echo "=========================================="

echo
echo "--- generator.py: импорты и ключевые блоки ---"
sed -n '1,30p'   "$BACKEND/apps/menu/generator.py"
echo "  ---- ... ----"
sed -n '95,170p' "$BACKEND/apps/menu/generator.py"
echo "  ---- ... ----"
sed -n '300,360p' "$BACKEND/apps/menu/generator.py"

echo
echo "--- generator.py: где raise EmptyRolePoolError и return items ---"
grep -nE "raise EmptyRolePoolError|return items|class MenuGenerator|def generate\b|_audit_empty_pool|_member_display_name|_recipe_cal" \
  "$BACKEND/apps/menu/generator.py"

echo
echo "--- views.py: блок генерации (130..200) ---"
sed -n '120,200p' "$BACKEND/apps/menu/views.py"

echo
echo "--- views.py: bulk_create блок MenuItem ---"
grep -nE "MenuItem.objects.bulk_create|generated = generator.generate|menu = Menu.objects.create|filters_used=filters" \
  "$BACKEND/apps/menu/views.py"

echo
echo "--- exceptions.py ---"
sed -n '1,99p' "$BACKEND/apps/menu/exceptions.py"

echo
echo "--- Recipe.nutrition пример структуры (для weight и servings_normalized) ---"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend python manage.py shell <<'PYEOF'
from apps.recipes.models import Recipe
import json
for rid in (3732, 440, 3392):
    try:
        r = Recipe.objects.get(id=rid)
    except Recipe.DoesNotExist:
        print(f"id={rid} not found"); continue
    print(f"--- id={r.id} title={r.title!r}")
    print(f"  food_group={r.food_group} servings={r.servings} servings_normalized={r.servings_normalized}")
    print(f"  nutrition={json.dumps(r.nutrition, ensure_ascii=False)[:250]}")
    pr = r.povar_raw or {}
    print(f"  povar_raw.dish_weight_g_calc={pr.get('dish_weight_g_calc')}")
PYEOF

echo
echo "--- MenuItem.MealType enum / DB значения ---"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend python manage.py shell <<'PYEOF'
from apps.menu.models import MenuItem
print("MealType choices:", MenuItem.MealType.choices)
print("ComponentRole choices:", MenuItem.ComponentRole.choices)
PYEOF

echo
echo "=========================================="
