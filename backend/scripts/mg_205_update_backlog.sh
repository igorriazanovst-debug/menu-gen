#!/usr/bin/env bash
# MG-205 финал: обновление MenuGen_Backlog.xlsx (с хоста)
#  1) MG-205: статус → ✅ Done
#  2) Добавить новую карточку MG-205-UI (P2, 4ч)
# Идемпотентен. Бэкап рядом с .xlsx.
# Запуск: bash /opt/menugen/backend/scripts/mg_205_update_backlog.sh

set -eu
PROJECT_ROOT="/opt/menugen"

echo "[i] поиск MenuGen_Backlog.xlsx..."
XLSX=$(find "${PROJECT_ROOT}" -maxdepth 4 -name "MenuGen_Backlog.xlsx" -not -path "*/.git/*" -not -path "*/backups/*" 2>/dev/null | head -1)
if [ -z "${XLSX}" ]; then
  echo "ERROR: MenuGen_Backlog.xlsx не найден в ${PROJECT_ROOT}"
  exit 1
fi
echo "    found: ${XLSX}"

# Готовим Python окружение на хосте (как в MG-203 mg_205_add_to_backlog.py)
PY=$(command -v python3 || command -v python)
if [ -z "${PY}" ]; then
  echo "ERROR: python3 не найден на хосте"
  exit 1
fi
echo "[i] python: ${PY}"

# openpyxl — устанавливаем в --user если нет
if ! ${PY} -c "import openpyxl" 2>/dev/null; then
  echo "[i] openpyxl отсутствует, устанавливаю --user..."
  ${PY} -m pip install --user openpyxl --quiet || ${PY} -m pip install --break-system-packages openpyxl --quiet
fi

XLSX="${XLSX}" ${PY} - <<'PYEOF'
import os, shutil
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

src = Path(os.environ["XLSX"])
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = src.with_suffix(src.suffix + f".bak_mg205_final_{ts}")
shutil.copy2(src, bak)
print(f"[backup] {bak}")

wb = load_workbook(src)
print(f"[i] sheets: {wb.sheetnames}")

# Берём лист Backlog или первый, если так не назван
sheet_name = "Backlog" if "Backlog" in wb.sheetnames else wb.sheetnames[0]
ws = wb[sheet_name]
print(f"[i] using sheet: '{sheet_name}'")

# Определяем колонки по первой строке
headers = {}
for col_idx, cell in enumerate(ws[1], start=1):
    if cell.value:
        headers[str(cell.value).strip()] = col_idx
print(f"[i] headers: {list(headers.keys())}")


def col(*names):
    for n in names:
        if n in headers:
            return headers[n]
    return None


col_id = col("ID", "id", "Ключ", "Key")
col_status = col("Статус", "Status", "статус")
col_desc = col("Описание", "Description", "описание", "Title", "Заголовок")
col_prio = col("Приоритет", "Priority", "приоритет", "P")
col_hours = col("Часов", "Hours", "Estimate", "Оценка", "часов")

if col_id is None or col_status is None or col_desc is None:
    print(f"ERROR: не нашёл обязательных колонок (ID/Status/Description). headers={headers}")
    raise SystemExit(1)

# Поиск MG-205 и проверка наличия MG-205-UI
mg205_row = None
mg205_ui_exists = False
last_data_row = 1
for row_idx in range(2, ws.max_row + 1):
    v = ws.cell(row=row_idx, column=col_id).value
    if v is None:
        continue
    last_data_row = row_idx
    v_str = str(v).strip()
    if v_str == "MG-205":
        mg205_row = row_idx
    if v_str == "MG-205-UI":
        mg205_ui_exists = True

# 1) MG-205 → Done
if mg205_row is None:
    print("[!] MG-205 не найдена — пропускаю обновление статуса")
else:
    cur_status = ws.cell(row=mg205_row, column=col_status).value
    cur_str = str(cur_status).strip() if cur_status else ""
    if cur_str.lower() in ("done", "✅", "✅ done"):
        print(f"[skip] MG-205 уже в статусе '{cur_status}'")
    else:
        ws.cell(row=mg205_row, column=col_status, value="✅ Done")
        ws.cell(row=mg205_row, column=col_status).font = Font(bold=True, color="006100")
        print(f"[update] MG-205 row={mg205_row}: '{cur_status}' → '✅ Done'")

# 2) MG-205-UI добавить
if mg205_ui_exists:
    print("[skip] MG-205-UI уже присутствует")
else:
    new_row = last_data_row + 1
    ws.cell(row=new_row, column=col_id, value="MG-205-UI")
    ws.cell(row=new_row, column=col_status, value="⏳ Todo")
    if col_prio:
        ws.cell(row=new_row, column=col_prio, value="P2")
    if col_hours:
        ws.cell(row=new_row, column=col_hours, value=4)
    ws.cell(
        row=new_row,
        column=col_desc,
        value=(
            "UI: бейджи источника правок КБЖУ (auto/user/specialist N) + "
            "кнопка 'Сбросить к авто' + история изменений в модалке. "
            "Зависит от: MG-205 (✅), MG-204."
        ),
    )
    fill = PatternFill(start_color="FFFFEB99", end_color="FFFFEB99", fill_type="solid")
    for c in range(1, ws.max_column + 1):
        ws.cell(row=new_row, column=c).fill = fill
    print(f"[add]  MG-205-UI вставлена в row={new_row}")

wb.save(src)
print(f"[done] saved → {src}")
print(f"[rollback] cp '{bak}' '{src}'")
PYEOF

echo
echo "=== mg_205_update_backlog done ==="
