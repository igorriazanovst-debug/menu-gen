#!/usr/bin/env bash
# Снять MenuGen_Backlog.xlsx из .gitignore, закрыть MG-204, закоммитить.
set -euo pipefail

cd /opt/menugen
TS="$(date +%Y%m%d_%H%M%S)"
GI=".gitignore"

echo "### 1. Текущие правила .gitignore, которые игнорируют xlsx ###"
grep -nE "xlsx|MenuGen_Backlog" "$GI" || echo "  не найдено явных правил"
echo

echo "### 2. git check-ignore -v (точное правило) ###"
git check-ignore -v MenuGen_Backlog.xlsx || true
echo

echo "### 3. Бэкап .gitignore ###"
cp "$GI" "/opt/menugen/backups/.gitignore.bak_${TS}"
echo "  → /opt/menugen/backups/.gitignore.bak_${TS}"
echo

echo "### 4. Удаляем правила, игнорирующие xlsx (комментируем + добавляем явный allow) ###"
python3 <<'PYEOF'
path = ".gitignore"
import re
with open(path, encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
changed = []
for i, ln in enumerate(lines, start=1):
    raw = ln.rstrip("\n")
    stripped = raw.strip()
    # пропускаем пустые и комментарии
    if not stripped or stripped.startswith("#"):
        new_lines.append(ln)
        continue
    # ищем правила, под которые подпадает .xlsx
    # типичные шаблоны: *.xlsx, **/*.xlsx, MenuGen_Backlog.xlsx, *.xls*
    is_xlsx_rule = (
        stripped.endswith(".xlsx")
        or stripped.endswith("*.xlsx")
        or stripped.endswith(".xls*")
        or "MenuGen_Backlog" in stripped
    )
    if is_xlsx_rule:
        new_lines.append(f"# [MG-204] disabled to track MenuGen_Backlog.xlsx: {raw}\n")
        changed.append((i, raw))
    else:
        new_lines.append(ln)

# добавим явный allow на всякий случай (если родительский каталог где-то игнорится)
allow_marker = "# [MG-204] explicit allow for MenuGen_Backlog.xlsx"
if allow_marker not in "".join(new_lines):
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines.append("\n")
    new_lines.append("\n")
    new_lines.append(allow_marker + "\n")
    new_lines.append("!MenuGen_Backlog.xlsx\n")

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Закомментированные правила:")
for i, r in changed:
    print(f"  line {i}: {r}")
if not changed:
    print("  (ни одного — наверное игнорируется глобальным .gitignore_global или родительским)")
PYEOF
echo

echo "### 5. Проверка: ignored ли теперь xlsx? ###"
if git check-ignore -v MenuGen_Backlog.xlsx; then
  echo "  ❌ всё ещё игнорируется! Покажу почему:"
  git check-ignore -v MenuGen_Backlog.xlsx
  exit 1
else
  echo "  ✅ больше не игнорируется"
fi
echo

echo "### 6. Закрыть MG-204 в xlsx (через mg_204_close_backlog.py) ###"
if [ -f /opt/menugen/backend/scripts/mg_204_close_backlog.py ]; then
  python3 /opt/menugen/backend/scripts/mg_204_close_backlog.py
else
  echo "  ⚠️ /opt/menugen/backend/scripts/mg_204_close_backlog.py не найден — пропускаю"
fi
echo

echo "### 7. git add + commit ###"
git add .gitignore MenuGen_Backlog.xlsx
git status --short | head -10
echo
git commit -m "MG-204: track MenuGen_Backlog.xlsx in git; close MG-204 (web)

- .gitignore: disable rule that excluded *.xlsx; explicit !MenuGen_Backlog.xlsx
- MenuGen_Backlog.xlsx: mark MG-204 as ✅ (web), mobile deferred"
echo
echo "✅ Done. Последний коммит:"
git log --oneline -2
