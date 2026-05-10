#!/bin/bash
# MG_505_V_diag_rest — что с остальными файлами после apply
set +e
ROOT=/opt/menugen

echo "=== маркеры MG_505 во всех файлах ==="
grep -rn "MG_505" "$ROOT/backend/apps/" "$ROOT/web/menugen-web/src/" 2>/dev/null

echo
echo "=== models.py: is_cheat_meal ==="
grep -n "is_cheat_meal" "$ROOT/backend/apps/menu/models.py"

echo
echo "=== serializers.py: is_cheat_meal в Meta.fields ==="
grep -n "is_cheat_meal" "$ROOT/backend/apps/menu/serializers.py"

echo
echo "=== views.py: is_cheat_meal и mark_cheat_meal_used ==="
grep -nE "is_cheat_meal|_mg505_mark_cheat_meal_used" "$ROOT/backend/apps/menu/views.py"

echo
echo "=== migrations: ==="
ls -la "$ROOT/backend/apps/menu/migrations/" | tail -10

echo
echo "=== типы фронта ==="
grep -n "is_cheat_meal" "$ROOT/web/menugen-web/src/types/index.ts" 2>/dev/null || echo "no match"

echo
echo "=== AST checks ==="
for f in apps/menu/models.py apps/menu/serializers.py apps/menu/views.py apps/menu/generator.py; do
    docker compose -f "$ROOT/docker-compose.yml" exec -T backend python -c "import ast; ast.parse(open('$f').read()); print('$f OK')"
done
