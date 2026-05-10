#!/bin/bash
# MG_505_V_backlog_update — пометить MG-504 и MG-505 как закрытые
set -e
BACKLOG=/opt/menugen/MenuGen_Backlog.xlsx
TS=$(date +%Y%m%d_%H%M%S)
cp "$BACKLOG" "/tmp/MenuGen_Backlog_${TS}.xlsx.bak"
echo "backup → /tmp/MenuGen_Backlog_${TS}.xlsx.bak"

python3 <<'PY'
from openpyxl import load_workbook
path = "/opt/menugen/MenuGen_Backlog.xlsx"
wb = load_workbook(path)
ws = wb["Backlog"]

# колонки: 1=ID, 2=Приоритет, 3=Категория, 4=Спринт, 5=Задача
updates = {
    "MG-504": "✅ Поля bedtime_hour и cheat_meal_interval в Profile",
    "MG-505": "✅ Слот cheat-meal в меню",
}

for row in ws.iter_rows(min_row=2, values_only=False):
    rid = row[0].value
    if rid in updates:
        old = row[4].value
        row[4].value = updates[rid]
        print(f"  {rid}: {old!r} → {updates[rid]!r}")

wb.save(path)
print("OK")
PY

echo
echo "=== проверка ==="
python3 <<'PY'
from openpyxl import load_workbook
wb = load_workbook("/opt/menugen/MenuGen_Backlog.xlsx")
ws = wb["Backlog"]
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0] in ("MG-504", "MG-505"):
        print(f"  {row[0]}: {row[4]}")
PY
