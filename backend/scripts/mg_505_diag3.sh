#!/bin/bash
F=/opt/menugen/backend/apps/menu/generator.py
echo "=== lines ==="; wc -l "$F"
echo
echo "=== 700-750 ==="
sed -n '700,750p' "$F"
