#!/bin/bash
F=/opt/menugen/backend/apps/menu/generator.py
echo "=== lines ==="; wc -l "$F"
echo
echo "=== все вхождения _audit_empty_pool ==="
grep -n "_audit_empty_pool" "$F"
echo
echo "=== все AuditLog в файле ==="
grep -n "AuditLog" "$F"
echo
echo "=== все вхождения 'cheat-meal слот' ==="
grep -n "cheat-meal слот" "$F"
echo
echo "=== строки 705-790 ==="
sed -n '705,790p' "$F"
