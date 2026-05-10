#!/bin/bash
# MG_505_V_update_backlog
set -e
BACKLOG=/opt/menugen/MenuGen_Backlog.xlsx
TS=$(date +%Y%m%d_%H%M%S)
cp "$BACKLOG" "/tmp/MenuGen_Backlog_${TS}.xlsx.bak"
echo "backup → /tmp/MenuGen_Backlog_${TS}.xlsx.bak"

# через docker (там openpyxl есть)
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python <<'PY'
from openpyxl import load_workbook
import shutil
src = "/opt/menugen/MenuGen_Backlog.xlsx"
dst = src
# в контейнере /opt/menugen смонтирован? проверим
import os
candidates = [
    "/opt/menugen/MenuGen_Backlog.xlsx",
    "/app/../MenuGen_Backlog.xlsx",
]
for c in candidates:
    if os.path.exists(c):
        src = c; dst = c
        break
print(f"file: {src}")
wb = load_workbook(src)
print(f"sheets: {wb.sheetnames}")
for sn in wb.sheetnames:
    ws = wb[sn]
    print(f"\n--- {sn} (rows={ws.max_row}) ---")
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 5), values_only=True):
        print("  ", row)
PY
