#!/bin/bash
# MG_505_V_fix_helpers_v3 — переносит helpers ПОСЛЕ полного _audit_empty_pool
set -e
F=/opt/menugen/backend/apps/menu/generator.py
TS=$(date +%Y%m%d_%H%M%S)
cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "backup → /tmp/mg_505_fix_${TS}_generator.py.bak"

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
src = open(path, encoding="utf-8").read()
lines = src.splitlines()

# найдём строку начала helpers-блока (def _mg505_is_cheat_day на верхнем уровне)
helpers_start = None
audit_method_start = None
for i, ln in enumerate(lines):
    if ln.startswith("def _mg505_is_cheat_day"):
        helpers_start = i
    if ln.startswith("    def _audit_empty_pool"):
        audit_method_start = i

if helpers_start is None:
    raise SystemExit("helpers_start not found")
if audit_method_start is None:
    raise SystemExit("audit_method_start not found")

# helpers — от helpers_start до конца блока (до строки `        profile.save(update_fields=["last_cheat_meal_date"])`)
# найдём конец helpers — это последняя строка до оторванного хвоста "            AuditLog.objects.create("
helpers_end = None
for i in range(helpers_start, len(lines)):
    if lines[i].strip().startswith("AuditLog.objects.create"):
        helpers_end = i  # эта строка уже не helpers
        break
if helpers_end is None:
    raise SystemExit("helpers_end not found (orphan AuditLog tail)")

helpers_block = lines[helpers_start:helpers_end]
# уберём пустые в конце
while helpers_block and helpers_block[-1].strip() == "":
    helpers_block.pop()

# хвост AuditLog (от helpers_end до конца файла) — это оторванный остаток _audit_empty_pool
audit_tail = lines[helpers_end:]
# уберём ведущие пустые
while audit_tail and audit_tail[0].strip() == "":
    audit_tail.pop(0)

# тело текущего _audit_empty_pool (от строки audit_method_start до helpers_start) обрезано на try-блоке
# восстановим: голова метода + audit_tail
# проверим: последняя строка перед helpers_start должна быть `            from apps.sync.models import AuditLog`
audit_head_block = lines[audit_method_start:helpers_start]
while audit_head_block and audit_head_block[-1].strip() == "":
    audit_head_block.pop()

# объединяем: всё ДО метода _audit_empty_pool + полный метод + helpers (модульный уровень)
before_audit = lines[:audit_method_start]
restored_audit = audit_head_block + audit_tail

new_lines = before_audit + restored_audit + ["", ""] + helpers_block + [""]
new_src = "\n".join(new_lines) + "\n"

open(path, "w", encoding="utf-8").write(new_src)
print("rewrote OK; lines =", len(new_lines))
PY

echo
echo "=== ast.parse check ==="
python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"

echo
echo "=== маркеры MG_505 ==="
grep -n "MG_505" "$F"

echo
echo "=== django check ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py check
