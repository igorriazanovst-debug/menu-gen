#!/usr/bin/env bash
# MG-204 fix MenuPage inject — убираем кривую вставку, ставим правильно
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
MP="$SRC/pages/Menu/MenuPage.tsx"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="/opt/menugen/backups"

cp "$MP" "$BACKUPS/MenuPage.tsx.bak_mg204fix_${TS}"
echo "backup → $BACKUPS/MenuPage.tsx.bak_mg204fix_${TS}"

python3 <<'PYEOF'
import re
path = "/opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx"
s = open(path, encoding='utf-8').read()

# 1. Удаляем кривую вставку (строки 539-540 в дампе):
#       {/* MG-204: дневная сводка КБЖУ */}
#       <DayNutritionSummary items={dayItems} targets={targets} />
bad_pat = re.compile(
    r"[ \t]*\{/\* MG-204: дневная сводка КБЖУ \*/\}\n[ \t]*<DayNutritionSummary items=\{dayItems\} targets=\{targets\} />\n",
    re.MULTILINE,
)
matches = list(bad_pat.finditer(s))
print(f"Bad inject occurrences: {len(matches)}")
s = bad_pat.sub("", s)

# 2. Правильная вставка: после строки <h3 ...>{dayLabel}</h3>, ВНУТРИ <Card>.
# Anchor:  <h3 className="font-semibold text-chocolate mb-3 capitalize">{dayLabel}</h3>
h3 = '<h3 className="font-semibold text-chocolate mb-3 capitalize">{dayLabel}</h3>'
if h3 not in s:
    raise SystemExit("h3{dayLabel} anchor not found in MenuPage.tsx")

# отступ берём от строки h3
i_h3 = s.find(h3)
line_start = s.rfind("\n", 0, i_h3) + 1
indent = ""
i = line_start
while i < i_h3 and s[i] in " \t":
    indent += s[i]
    i += 1

inject = (
    f"\n{indent}{{/* MG-204: дневная сводка КБЖУ */}}\n"
    f"{indent}<DayNutritionSummary items={{dayItems}} targets={{targets}} />"
)

# вставляем сразу ПОСЛЕ </h3>
new_block = h3 + inject
# защитимся от двойной вставки
if "DayNutritionSummary items={dayItems} targets={targets}" not in s:
    s = s.replace(h3, new_block, 1)
    print("Inserted DayNutritionSummary after h3{dayLabel}")
else:
    # если уже было, всё равно проверим что осталась только одна корректная вставка
    pass

open(path, 'w', encoding='utf-8').write(s)
print("Saved")
PYEOF

echo
echo "### tsc проверка ###"
cd "$WEB"
npx tsc --noEmit 2>&1 | tee /tmp/mg_204_tsc.log
RC=$?
echo
if [ $RC -eq 0 ]; then
  echo "tsc OK ✅"
fi
echo
echo "Откат фикса (вернёт версию ДО этого фикс-скрипта, но ПОСЛЕ apply):"
echo "  cp $BACKUPS/MenuPage.tsx.bak_mg204fix_${TS} $MP"
