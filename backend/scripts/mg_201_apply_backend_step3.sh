#!/usr/bin/env bash
# MG-201 STEP 3 — переименовать локальную переменную meal_plan -> meal_count
# в /opt/menugen/backend/apps/menu/generator.py
# Идемпотентно: если уже meal_count — пропускаем.

set -euo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
F="$ROOT/backend/apps/menu/generator.py"
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/$(basename "$F").bak_mg201_${TS}"

echo "================================================================"
echo "MG-201 STEP 3 — local var rename meal_plan -> meal_count"
echo "  файл:   $F"
echo "  бэкап:  $BAK"
echo "================================================================"

if [[ ! -f "$F" ]]; then
  echo "[!] файл не найден"; exit 1
fi

# Идемпотентность
if ! grep -qE '^\s*meal_plan\s*=\s*self\.filters\.get' "$F"; then
  echo "[skip] локальной переменной meal_plan = self.filters.get(...) не нашли — возможно уже переименовано"
  echo
  grep -nE 'meal_plan|meal_count' "$F" | sed 's/^/  /'
  exit 0
fi

cp "$F" "$BAK"

python3 - "$F" <<'PYEOF'
import re, sys
path = sys.argv[1]
src = open(path, encoding='utf-8').read()
orig = src

# Меняем строку объявления:
#   meal_plan = self.filters.get("meal_plan_type", "3")
# -> meal_count = self.filters.get("meal_plan_type", "3")
src = re.sub(
    r'(\bmeal_plan\b)(\s*=\s*self\.filters\.get\(\s*["\']meal_plan_type["\'])',
    r'meal_count\2',
    src,
)

# Меняем использование на след. строке (или рядом):
#   ... if str(meal_plan) == "5" ...
# и любые другие чтения переменной meal_plan, которые НЕ являются ключом строки
# и не идут после точки (то есть не атрибут).
# Безопасно: meal_plan встречается только локально по результату grep.
# Ограничим только теми вхождениями, которые НЕ внутри кавычек.
def replace_outside_strings(s, frm, to):
    out = []
    i = 0
    in_str = None  # текущая кавычка ' или " или None
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < len(s):
                out.append(s[i+1]); i += 2; continue
            if ch == in_str:
                in_str = None
            i += 1
        else:
            if ch in ('"', "'"):
                in_str = ch
                out.append(ch); i += 1
                continue
            # whole-word match
            if s.startswith(frm, i):
                # граничные условия: до — не буква/цифра/_, после — не буква/цифра/_
                left_ok  = (i == 0) or not (s[i-1].isalnum() or s[i-1] == '_')
                right_ok = (i + len(frm) == len(s)) or not (s[i+len(frm)].isalnum() or s[i+len(frm)] == '_')
                if left_ok and right_ok:
                    out.append(to); i += len(frm); continue
            out.append(ch); i += 1
    return ''.join(out)

src = replace_outside_strings(src, 'meal_plan', 'meal_count')

if src != orig:
    open(path, 'w', encoding='utf-8').write(src)
    print('  заменено')
else:
    print('  без изменений')
PYEOF

# Контроль
if grep -qE '\bmeal_plan\b' "$F"; then
  echo "[!] остатки meal_plan:"
  grep -nE '\bmeal_plan\b' "$F" | sed 's/^/    /'
  echo "[!] откат"
  cp "$BAK" "$F"
  exit 1
fi

echo
echo "[diff] изменённые строки:"
diff -u "$BAK" "$F" || true

# Smoke
echo
echo "[smoke] manage.py check..."
docker compose -f "$COMPOSE" exec -T backend python manage.py check

echo
echo "[smoke] импорт generator..."
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.menu import generator
print('  ok, MenuGenerator =', generator.MenuGenerator)
"

echo
echo "================================================================"
echo "STEP 3 ГОТОВО.  Откат: cp $BAK $F"
echo "================================================================"
