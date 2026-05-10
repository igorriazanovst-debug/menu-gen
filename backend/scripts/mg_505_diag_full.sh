#!/bin/bash
# MG_505_V_diag_full — что в текущем файле и в бэкапе ДО apply
F=/opt/menugen/backend/apps/menu/generator.py
BAK=/tmp/mg_505_backup_20260510_120750/apps/menu/generator.py

echo "============================================"
echo " ТЕКУЩИЙ файл $F"
echo "============================================"
wc -l "$F"
echo
echo "--- маркеры MG_505 в ТЕКУЩЕМ ---"
grep -n "MG_505" "$F"
echo
echo "--- маркеры MG_502_503 в ТЕКУЩЕМ (для контроля) ---"
grep -n "MG_502_503" "$F"

echo
echo "============================================"
echo " БЭКАП ДО apply $BAK"
echo "============================================"
wc -l "$BAK"
echo
echo "--- маркеры MG_505 в БЭКАПЕ (должно быть 0) ---"
grep -n "MG_505" "$BAK" || echo "NONE — ожидаемо"
echo
echo "--- маркеры MG_502_503 в БЭКАПЕ ---"
grep -n "MG_502_503" "$BAK"
echo
echo "--- маркеры MG_303 в БЭКАПЕ ---"
grep -nc "MG_303" "$BAK"
echo
echo "--- маркеры MG_302 в БЭКАПЕ ---"
grep -nc "MG_302" "$BAK"
echo
echo "--- маркеры MG_301 в БЭКАПЕ ---"
grep -nc "MG_301" "$BAK"
