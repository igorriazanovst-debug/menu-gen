#!/bin/bash
# MG_505_V_fix_helpers — восстанавливает _audit_empty_pool и переносит helpers в конец файла
set -e
F=/opt/menugen/backend/apps/menu/generator.py
BAK_DIR=/tmp/mg_505_backup_20260510_120750
BAK_FILE="${BAK_DIR}/apps/menu/generator.py"
TS=$(date +%Y%m%d_%H%M%S)

cp "$F" "/tmp/mg_505_fix_${TS}_generator.py.bak"
echo "current backup → /tmp/mg_505_fix_${TS}_generator.py.bak"

if [ ! -f "$BAK_FILE" ]; then
    echo "ORIG BACKUP NOT FOUND: $BAK_FILE"; exit 1
fi

python3 <<'PY'
path = "/opt/menugen/backend/apps/menu/generator.py"
bak  = "/tmp/mg_505_backup_20260510_120750/apps/menu/generator.py"

cur = open(path, encoding="utf-8").read()
orig = open(bak,  encoding="utf-8").read()

marker = "# MG_505_V_generator: cheat-meal слот"
i = cur.find(marker)
if i == -1:
    raise SystemExit("MARKER NOT FOUND")

# вырезаем блок helpers целиком (от маркера до конца)
helpers = cur[i:].rstrip() + "\n"

# восстановим хвост файла из оригинала (метод _audit_empty_pool целиком)
# в оригинале метод начинается с "    def _audit_empty_pool" — найдём индекс
oi = orig.rfind("    def _audit_empty_pool(self, err, member) -> None:")
if oi == -1:
    raise SystemExit("ORIG _audit_empty_pool NOT FOUND")
orig_tail = orig[oi:].rstrip() + "\n"

# в текущем файле найдём начало метода _audit_empty_pool и обрежем до него
ci = cur.rfind("    def _audit_empty_pool(self, err, member) -> None:", 0, i)
if ci == -1:
    raise SystemExit("CUR _audit_empty_pool NOT FOUND")

head = cur[:ci].rstrip() + "\n"

new_src = head + "\n" + orig_tail + "\n\n" + helpers
open(path, "w", encoding="utf-8").write(new_src)
print("rewrote OK; lines =", new_src.count("\n"))
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
