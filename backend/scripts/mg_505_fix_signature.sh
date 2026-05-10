#!/bin/bash
# MG_505_V_fix_signature — добавить is_cheat в сигнатуру _pick_for_role
set -e
F=/opt/menugen/backend/apps/menu/generator.py
TS=$(date +%Y%m%d_%H%M%S)
cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "backup → /tmp/mg_505_fix_${TS}_generator.py.bak"

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
src = open(path, encoding="utf-8").read()
old = "        member_id: int,\n        day_offset: int,\n    ) -> Optional[Recipe]:"
new = "        member_id: int,\n        day_offset: int,\n        is_cheat: bool = False,  # MG_505_V_pick_bypass\n    ) -> Optional[Recipe]:"
if old not in src:
    raise SystemExit("signature pattern not found")
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("OK")
PY

echo
echo "=== ast.parse ==="
python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"

echo
echo "=== сигнатура ==="
sed -n '430,445p' "$F"

echo
echo "=== django check ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py check

echo
echo "=== pytest ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/ apps/users/ apps/family/ -q --tb=short 2>&1 | tail -40
