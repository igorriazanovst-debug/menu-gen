#!/bin/bash
# MG_505_V_backlog_inspect_v2
set -e
BACKLOG=/opt/menugen/MenuGen_Backlog.xlsx

# проверка openpyxl на хосте
python3 -c "import openpyxl" 2>/dev/null || pip3 install --break-system-packages openpyxl

python3 <<PY
from openpyxl import load_workbook
wb = load_workbook("$BACKLOG")
print("sheets:", wb.sheetnames)
for sn in wb.sheetnames:
    ws = wb[sn]
    print(f"\n=== {sn} (rows={ws.max_row}, cols={ws.max_column}) ===")
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        print(f"  {i}: {row}")
PY
