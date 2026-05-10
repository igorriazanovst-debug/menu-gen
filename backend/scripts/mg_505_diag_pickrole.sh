#!/bin/bash
F=/opt/menugen/backend/apps/menu/generator.py
echo "=== _pick_for_role сигнатура и шапка ==="
sed -n '430,475p' "$F"
