#!/bin/bash
# MG_505_V_diag_syntax — найти куда вставлен import и контекст вокруг строки 714
set -e
F=/opt/menugen/backend/apps/menu/generator.py

echo "=== TOTAL LINES ==="
wc -l "$F"

echo
echo "=== СТРОКИ 700-740 ==="
sed -n '700,740p' "$F"

echo
echo "=== ВСЕ MG_505 МАРКЕРЫ ==="
grep -n "MG_505" "$F" || echo "no markers"

echo
echo "=== ВСЕ _mg505_ упоминания (line numbers) ==="
grep -n "_mg505_" "$F" || echo "no _mg505_"

echo
echo "=== Поиск try: блоков и их закрытий рядом со строкой 714 ==="
sed -n '670,720p' "$F"

echo
echo "=== Файл-бэкап (последний) ==="
ls -la /tmp/mg_505_backup_*/generator.py 2>/dev/null | tail -3
