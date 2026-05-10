#!/bin/bash
F1=/opt/menugen/backend/apps/menu/views.py
F2=/opt/menugen/web/menugen-web/src/types/index.ts

echo "=== views.py 175-215 ==="
sed -n '175,215p' "$F1"

echo
echo "=== views.py все импорты сверху файла ==="
sed -n '1,40p' "$F1"

echo
echo "=== types.ts: MenuItem интерфейс ==="
grep -n -A 20 "interface MenuItem" "$F2" 2>/dev/null

echo
echo "=== types.ts: все упоминания cheat ==="
grep -n "cheat" "$F2" 2>/dev/null || echo "no cheat in types.ts"
