#!/bin/bash
# MG_505_V_fix_helpers_v5 — заменить сломанный _audit_empty_pool корректным из бэкапа
set -e
F=/opt/menugen/backend/apps/menu/generator.py
BAK=/tmp/mg_505_backup_20260510_120750/apps/menu/generator.py
TS=$(date +%Y%m%d_%H%M%S)
cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "current → /tmp/mg_505_fix_${TS}_generator.py.bak"

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
bak  = "/tmp/mg_505_backup_20260510_120750/apps/menu/generator.py"

cur = open(path, encoding="utf-8").read()
orig = open(bak,  encoding="utf-8").read()

# 1. Извлекаем корректный метод _audit_empty_pool из бэкапа целиком
#    (он в бэкапе последний — до конца файла)
audit_def = "    def _audit_empty_pool(self, err, member) -> None:"
oi = orig.find(audit_def)
if oi == -1:
    raise SystemExit("ORIG audit method not found")
# в бэкапе метод — до конца файла
audit_method = orig[oi:].rstrip() + "\n"

# 2. В текущем файле находим начало сломанного _audit_empty_pool
ci = cur.find(audit_def)
if ci == -1:
    raise SystemExit("CUR audit method not found")

# 3. И находим начало helpers-блока MG_505_V_generator
helpers_marker = "# MG_505_V_generator: cheat-meal слот"
hi = cur.find(helpers_marker)
if hi == -1:
    raise SystemExit("CUR helpers marker not found")

# 4. Собираем: head [до сломанного метода] + правильный метод + 2 пустые + helpers [от маркера до конца]
head    = cur[:ci].rstrip() + "\n"
helpers = cur[hi:].rstrip() + "\n"

new_src = head + audit_method + "\n\n" + helpers
open(path, "w", encoding="utf-8").write(new_src)
print("OK; lines =", new_src.count("\n"))
PY

echo
echo "=== ast.parse ==="
python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"

echo
echo "=== маркеры MG_505 ==="
grep -n "MG_505" "$F"

echo
echo "=== маркеры MG_502_503 (контроль не сломали) ==="
grep -nc "MG_502_503" "$F"

echo
echo "=== django check ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py check
