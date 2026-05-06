#!/bin/bash
set -uo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
F="$ROOT/backend/apps/menu/generator.py"

echo "=== generator.py: маркеры/методы ==="
grep -nE "MG_304_V_generator|_ensure_veg_fruit_servings|self\.last_warnings|return items" "$F" || true

echo
echo "=== class: атрибуты MenuGenerator (через shell -c) ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.menu.generator import MenuGenerator
print('class methods with veg_fruit:', [a for a in dir(MenuGenerator) if 'veg_fruit' in a or 'last_warnings' in a])
print('hasattr class _ensure_veg_fruit_servings:', hasattr(MenuGenerator, '_ensure_veg_fruit_servings'))
"

echo
echo "=== run pytest MG-304 only ==="
docker compose -f "$COMPOSE" exec -T backend pytest apps/menu/tests/test_mg_304.py -q 2>&1 | tail -25
