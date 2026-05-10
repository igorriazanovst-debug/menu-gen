#!/bin/bash
# MG_505_V_diag2 — текущее состояние generator.py
set -e
F=/opt/menugen/backend/apps/menu/generator.py

echo "=== lines ==="
wc -l "$F"

echo
echo "=== строки 740-790 (где сломано) ==="
sed -n '740,790p' "$F"

echo
echo "=== строки 690-715 (граница головы и хвоста) ==="
sed -n '690,715p' "$F"

echo
echo "=== есть ли class в файле, где он начинается? ==="
grep -n "^class " "$F"

echo
echo "=== все def на верхнем уровне модуля и в классе ==="
grep -nE "^(    )?def " "$F" | tail -30
