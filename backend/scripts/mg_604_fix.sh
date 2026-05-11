#!/usr/bin/env bash
# MG-604 fix: добавить тест для покрытия строк 81-82 в portions.py
# (exception в блоке nutrition, при этом nut должен быть dict)
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"

TEST="$BACKEND/apps/menu/tests/test_mg_604_portions.py"

echo "=========================================="
echo "  MG-604 FIX portions.py 81-82"
echo "=========================================="

python3 <<PYEOF
import sys

PATH = "$TEST"
src = open(PATH).read()

# Заменяем тест nutrition_exception_falls_through_to_povar — он был некорректным
# (BoomDict не isinstance(dict), поэтому ветка nut.get() не выполнялась).
# Делаем dict-подкласс, у которого .get() бросает.
old = '''    def test_nutrition_exception_falls_through_to_povar(self):
        """Покрывает 81-82: exception в блоке nutrition → переход к povar_raw."""
        class BoomDict:
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            nutrition = BoomDict()
            povar_raw = {"dish_weight_g_calc": 400}
            servings = 2
            servings_normalized = None
        # nutrition вылетит, povar_raw даст 400/2 = 200
        assert recipe_portion_grams(R()) == 200.0'''

new = '''    def test_nutrition_exception_falls_through_to_povar(self):
        """Покрывает 81-82: exception в блоке nutrition → переход к povar_raw.

        Важно: BoomDict должен быть подклассом dict, чтобы пройти isinstance,
        иначе ветка nut.get(...) не выполняется.
        """
        class BoomDict(dict):
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            nutrition = BoomDict()
            povar_raw = {"dish_weight_g_calc": 400}
            servings = 2
            servings_normalized = None
        # nutrition вылетит, povar_raw даст 400/2 = 200
        assert recipe_portion_grams(R()) == 200.0'''

if old not in src:
    print("ERR: блок не найден"); sys.exit(2)
src = src.replace(old, new)
open(PATH, "w").write(src)
print("OK: BoomDict теперь подкласс dict")
PYEOF

$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/tests/test_mg_604_portions.py').read()); print('AST OK')"

echo
echo "--- pytest portions ---"
$COMPOSE exec -T backend pytest apps/menu/tests/test_mg_604_portions.py -v --tb=short 2>&1 | tail -10

echo
echo "--- coverage report ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing
'

echo "=========================================="
echo "  MG-604 FIX DONE"
echo "=========================================="
