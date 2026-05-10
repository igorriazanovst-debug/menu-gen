#!/bin/bash
# MG_505_V_fix_zero_interval — корректная обработка interval=0
set -e
F=/opt/menugen/backend/apps/menu/generator.py
TS=$(date +%Y%m%d_%H%M%S)
cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "backup → /tmp/mg_505_fix_${TS}_generator.py.bak"

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
src = open(path, encoding="utf-8").read()
old = '    interval = getattr(profile, "cheat_meal_interval", None) or CHEAT_MEAL_DEFAULT_INTERVAL\n    if interval <= 0:\n        return False'
new = '''    _interval = getattr(profile, "cheat_meal_interval", None)
    interval = _interval if _interval is not None else CHEAT_MEAL_DEFAULT_INTERVAL
    if interval <= 0:
        return False'''
if old not in src:
    raise SystemExit("pattern not found")
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("OK")
PY

echo
echo "=== ast.parse ==="
python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"

echo
echo "=== pytest test_mg_505 ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/tests/test_mg_505.py -v --tb=short 2>&1 | tail -25

echo
echo "=== полная регрессия ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/ apps/users/ apps/family/ -q --tb=short 2>&1 | tail -15
