#!/bin/bash
# MG_505_V_finalize — миграция MenuItem.is_cheat_meal + types.ts + регрессия
set -e
ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TYPES="$ROOT/web/menugen-web/src/types/index.ts"
TS=$(date +%Y%m%d_%H%M%S)

# 1. types.ts — добавить is_cheat_meal в MenuItem
cp "$TYPES" "/tmp/mg_505_types_${TS}.bak"
echo "[1] backup types.ts → /tmp/mg_505_types_${TS}.bak"

if grep -q "is_cheat_meal" "$TYPES"; then
    echo "    уже патчен"
else
    python3 <<PY
path = "$TYPES"
src = open(path, encoding="utf-8").read()
old = "  recipe: Recipe; member_name?: string; quantity: number;\n}"
new = '  recipe: Recipe; member_name?: string; quantity: number;\n  is_cheat_meal?: boolean; // MG_505_V_types\n}'
if old not in src:
    raise SystemExit("MenuItem block not found")
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("    types.ts patched")
PY
fi

echo
echo "[2] grep types.ts ==="
grep -n "is_cheat_meal\|MG_505_V_types" "$TYPES"

echo
echo "[3] makemigrations menu ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py makemigrations menu

echo
echo "[4] список миграций ==="
ls -la "$ROOT/backend/apps/menu/migrations/" | tail -5

echo
echo "[5] migrate ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py migrate menu

echo
echo "[6] django check ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py check

echo
echo "[7] pytest apps/menu apps/users apps/family ==="
docker compose -f "$COMPOSE" exec -T backend pytest apps/menu/ apps/users/ apps/family/ -q --tb=short 2>&1 | tail -50
