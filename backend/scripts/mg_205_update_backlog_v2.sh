#!/usr/bin/env bash
# MG-205 финал v2: обновление MenuGen_Backlog.xlsx с реальной структурой
# Колонки: ID, Приоритет, Категория, Спринт, Задача, Описание,
#          Затрагиваемые файлы, Промпт для Claude, Зависит от, Оценка (ч)
# Идемпотентен.
set -eu
PROJECT_ROOT="/opt/menugen"

XLSX=$(find "${PROJECT_ROOT}" -maxdepth 4 -name "MenuGen_Backlog.xlsx" -not -path "*/.git/*" -not -path "*/backups/*" 2>/dev/null | head -1)
if [ -z "${XLSX}" ]; then
  echo "ERROR: MenuGen_Backlog.xlsx не найден"
  exit 1
fi
echo "[i] xlsx: ${XLSX}"

PY=$(command -v python3 || command -v python)
${PY} -c "import openpyxl" 2>/dev/null || ${PY} -m pip install --user openpyxl --quiet || ${PY} -m pip install --break-system-packages openpyxl --quiet

XLSX="${XLSX}" ${PY} - <<'PYEOF'
import os, shutil
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

src = Path(os.environ["XLSX"])
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = src.with_suffix(src.suffix + f".bak_mg205_final_{ts}")
shutil.copy2(src, bak)
print(f"[backup] {bak}")

wb = load_workbook(src)
ws = wb["Backlog"]

# Колонки (по реальному заголовку)
H = {}
for i, c in enumerate(ws[1], 1):
    if c.value:
        H[str(c.value).strip()] = i

req = ["ID", "Приоритет", "Категория", "Спринт", "Задача", "Описание",
       "Затрагиваемые файлы", "Промпт для Claude", "Зависит от", "Оценка (ч)"]
for r in req:
    if r not in H:
        print(f"ERROR: колонка '{r}' не найдена. Есть: {list(H.keys())}")
        raise SystemExit(1)
print(f"[i] columns OK")

# Поиск MG-205 и MG-205-UI
mg205_row = None
mg205_ui_exists = False
last_data_row = 1
for r in range(2, ws.max_row + 1):
    v = ws.cell(row=r, column=H["ID"]).value
    if v is None:
        continue
    last_data_row = r
    s = str(v).strip()
    if s == "MG-205":
        mg205_row = r
    if s == "MG-205-UI":
        mg205_ui_exists = True

# 1) MG-205 → done. Маркер "✅" в начало "Задача" (т.к. колонки Status нет).
if mg205_row is None:
    print("[!] MG-205 не найдена в листе")
else:
    task_cell = ws.cell(row=mg205_row, column=H["Задача"])
    cur = str(task_cell.value or "").strip()
    if cur.startswith("✅"):
        print(f"[skip] MG-205 уже отмечена как ✅ ('{cur[:60]}...')")
    else:
        task_cell.value = f"✅ {cur}"
        task_cell.font = Font(bold=True, color="006100")
        print(f"[update] MG-205 row={mg205_row} → '✅ {cur[:60]}...'")

# 2) Добавить MG-205-UI
if mg205_ui_exists:
    print("[skip] MG-205-UI уже есть")
else:
    new_row = last_data_row + 1

    # Возьмём Спринт и Категорию из MG-205, если есть
    sprint_val = "Спринт 2"
    cat_val = "Профиль и КБЖУ"
    if mg205_row:
        sv = ws.cell(row=mg205_row, column=H["Спринт"]).value
        cv = ws.cell(row=mg205_row, column=H["Категория"]).value
        if sv:
            sprint_val = sv
        if cv:
            cat_val = cv

    values = {
        "ID": "MG-205-UI",
        "Приоритет": "P2",
        "Категория": cat_val,
        "Спринт": sprint_val,
        "Задача": "UI: бейджи источника правок КБЖУ + кнопка 'Сбросить к авто' + история",
        "Описание": (
            "На фронте (React) и в мобайле (Flutter) для каждого поля КБЖУ "
            "(calorie/protein/fat/carb/fiber_target_g) показывать бейдж источника: "
            "«авто» / «вручную» / «диетолог N». Кнопка «Сбросить к авто» рядом — "
            "вызывает API force-сброса. По клику на бейдж — модалка с историей правок "
            "(ProfileTargetAudit), показывающая time/source/by_user/value."
        ),
        "Затрагиваемые файлы": (
            "web/menugen-web/src/pages/Profile/ProfilePage.tsx, "
            "web/menugen-web/src/types/index.ts, "
            "mobile/menugen_app/lib/screens/profile/, "
            "backend: новый endpoint POST /api/v1/users/me/targets/{field}/reset, "
            "backend: GET /api/v1/users/me/targets/{field}/history"
        ),
        "Промпт для Claude": (
            "Реализовать UI поверх данных MG-205. Backend: добавить два endpoint'а — "
            "GET history (список ProfileTargetAudit по полю) и POST reset "
            "(вызывает fill_profile_targets(force=True, actor=request.user) "
            "только для одного поля). На фронте: компонент <TargetField/> с бейджем "
            "и dropdown'ом-историей. Аналогично в Flutter. Тесты: API + UI snapshot. "
            "Зависит от: MG-205 (✅) и MG-204."
        ),
        "Зависит от": "MG-205, MG-204",
        "Оценка (ч)": 4,
    }

    for name, val in values.items():
        ws.cell(row=new_row, column=H[name], value=val)

    fill = PatternFill(start_color="FFFFEB99", end_color="FFFFEB99", fill_type="solid")
    for c in range(1, ws.max_column + 1):
        ws.cell(row=new_row, column=c).fill = fill
        ws.cell(row=new_row, column=c).alignment = Alignment(wrap_text=True, vertical="top")
    print(f"[add] MG-205-UI вставлена в row={new_row}")

wb.save(src)
print(f"[done] saved → {src}")
print(f"[rollback] cp '{bak}' '{src}'")
PYEOF

echo
echo "=== mg_205_update_backlog v2 done ==="
