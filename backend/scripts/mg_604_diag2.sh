#!/usr/bin/env bash
# MG-604 diag: почему portions.py строки 81-82 не покрылись
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=========================================="
echo "  MG-604 PORTIONS DIAG"
echo "=========================================="

echo
echo "--- [1] Текущий блок 1 portions.py (строки 65-85) ---"
$COMPOSE exec -T backend sed -n '65,85p' apps/menu/portions.py | cat -n

echo
echo "--- [2] Ручная проверка: что происходит с BoomDict(dict) ---"
$COMPOSE exec -T backend python manage.py shell <<'PYEOF'
class BoomDict(dict):
    def get(self, *a, **kw):
        raise RuntimeError("boom")

bd = BoomDict()
print("isinstance(bd, dict):", isinstance(bd, dict))
print("(bd or {}):", bd or {})  # bd пустой → falsy → подменяется на {}
print("(bd or {}) is bd:", (bd or {}) is bd)
print()

# Если bd пустой — он falsy → `nut or {}` подменит на пустой dict
# Поэтому до bd.get() мы не дойдём
# Нужно сделать BoomDict не-пустым:
bd2 = BoomDict({"x": 1})
print("len(bd2):", len(bd2))
print("isinstance(bd2, dict):", isinstance(bd2, dict))
print("(bd2 or {}) is bd2:", (bd2 or {}) is bd2)
try:
    bd2.get("weight")
except RuntimeError as e:
    print("bd2.get raised:", e)

# Симулируем работу recipe_portion_grams
from apps.menu.portions import recipe_portion_grams
class R:
    nutrition = bd2  # ← не пустой dict с .get → RuntimeError
    povar_raw = {"dish_weight_g_calc": 400}
    servings = 2
    servings_normalized = None
print()
print("recipe_portion_grams:", recipe_portion_grams(R()))
PYEOF

echo
echo "=========================================="
