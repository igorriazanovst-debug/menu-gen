#!/bin/bash
# MG_505_V_diag_backup — смотрим оригинальный _audit_empty_pool
set -e

# найти самый свежий бэкап с generator.py
BAK_DIR=$(ls -td /tmp/mg_505_backup_*/ 2>/dev/null | head -1)
if [ -z "$BAK_DIR" ]; then
    echo "NO BACKUP DIR"; exit 1
fi
BAK_FILE="${BAK_DIR}generator.py"
if [ ! -f "$BAK_FILE" ]; then
    # бэкап мог лежать в другой структуре
    find /tmp/mg_505_backup_* -name 'generator.py' 2>/dev/null
    BAK_FILE=$(find /tmp/mg_505_backup_* -name 'generator.py' 2>/dev/null | head -1)
fi
echo "backup: $BAK_FILE"

echo
echo "=== TOTAL LINES в бэкапе ==="
wc -l "$BAK_FILE"

echo
echo "=== оригинальный _audit_empty_pool (от def до конца файла или следующего def) ==="
awk '/def _audit_empty_pool/{flag=1} flag{print NR": "$0} flag && /^    def |^class /{if(NR>start+1)exit} /def _audit_empty_pool/{start=NR}' "$BAK_FILE" | head -80

echo
echo "=== строки 700-770 бэкапа ==="
sed -n '700,770p' "$BAK_FILE"

echo
echo "=== последние 30 строк бэкапа ==="
tail -30 "$BAK_FILE"
