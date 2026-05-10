#!/bin/bash
# MG_505_V_install_tests
set -e
SRC=/tmp/test_mg_505.py
DST=/opt/menugen/backend/apps/menu/tests/test_mg_505.py

if [ ! -f "$SRC" ]; then
    echo "ERROR: $SRC не найден. Сначала scp test_mg_505.py в /tmp/"
    exit 1
fi

cp "$SRC" "$DST"
echo "[1] установлен → $DST"

echo
echo "[2] AST check ==="
python3 -c "import ast; ast.parse(open('$DST').read()); print('OK')"

echo
echo "[3] pytest test_mg_505 ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/tests/test_mg_505.py -v --tb=short 2>&1 | tail -60

echo
echo "[4] Полная регрессия ==="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/ apps/users/ apps/family/ -q --tb=short 2>&1 | tail -30
