#!/bin/bash
# MG_505_V_fix_v6 — удалить оторванный AuditLog-блок между helpers
set -e
F=/opt/menugen/backend/apps/menu/generator.py
TS=$(date +%Y%m%d_%H%M%S)
cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "current → /tmp/mg_505_fix_${TS}_generator.py.bak"

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
src = open(path, encoding="utf-8").read()
lines = src.splitlines()

# Найти границы:
#  start_idx — строка `CHEAT_MEAL_SLOTS = ("lunch", "dinner")...`
#  end_idx   — строка перед `def _mg505_is_cheat_day(member, current_date):`
start_idx = None
end_idx = None
for i, ln in enumerate(lines):
    if ln.startswith("CHEAT_MEAL_SLOTS = "):
        start_idx = i
    if ln.startswith("def _mg505_is_cheat_day"):
        end_idx = i
        break

if start_idx is None or end_idx is None:
    raise SystemExit("borders not found")

# всё между start_idx (НЕ включая) и end_idx (НЕ включая) кроме пустых — это garbage
garbage = lines[start_idx+1:end_idx]
print(f"removing {len(garbage)} lines between {start_idx+1} and {end_idx-1}")

# собираем: head [включая start_idx] + 2 пустые + tail [от end_idx]
new_lines = lines[:start_idx+1] + ["", ""] + lines[end_idx:]
new_src = "\n".join(new_lines) + "\n"
open(path, "w", encoding="utf-8").write(new_src)
print("OK; lines =", len(new_lines))
PY

echo
echo "=== ast.parse ==="
python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"

echo
echo "=== маркеры MG_505 ==="
grep -n "MG_505" "$F"

echo
echo "=== AuditLog (должно остаться 1 import + 1 create) ==="
grep -n "AuditLog" "$F"

echo
echo "=== django check ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py check
