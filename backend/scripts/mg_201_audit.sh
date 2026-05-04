#!/usr/bin/env bash
# MG-201 audit: ищет упоминания старых имён полей в проекте.
# Запускать на хосте из любой директории.
#
# Усл. имена:
#   carbs_target_g  -> хотим переименовать в carb_target_g
#   meal_plan       -> хотим переименовать в meal_plan_type (учесть что meal_plan_type может уже быть)
#
# Результат: /tmp/mg201_audit.tsv  (поле<TAB>файл<TAB>строка<TAB>контекст)

set -euo pipefail

ROOT="/opt/menugen"
OUT="/tmp/mg201_audit.tsv"

# Корни поиска: backend/web/mobile. Если каких-то нет — пропускаем.
ROOTS=()
for d in "$ROOT/backend" "$ROOT/web" "$ROOT/mobile"; do
  [[ -d "$d" ]] && ROOTS+=("$d")
done

# Что игнорируем
EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=node_modules
  --exclude-dir=__pycache__
  --exclude-dir=.venv
  --exclude-dir=venv
  --exclude-dir=build
  --exclude-dir=dist
  --exclude-dir=.dart_tool
  --exclude-dir=.next
  --exclude-dir=migrations   # сами миграции отдельно посмотрим
  --exclude=*.pyc
  --exclude=*.lock
  --exclude=*.map
  --exclude=*.min.js
)

echo -e "field\tfile\tline\tcontent" > "$OUT"

# grep пишет: путь:строка:контент
# Преобразуем в TSV с полем-меткой.
search() {
  local label="$1"; shift
  local pattern="$1"; shift
  for r in "${ROOTS[@]}"; do
    grep -rEn "${EXCLUDES[@]}" "$pattern" "$r" 2>/dev/null \
      | awk -v lbl="$label" -F: '
          {
            file=$1; line=$2; $1=""; $2=""; sub(/^::/,"");
            gsub(/\t/," ", $0);
            printf "%s\t%s\t%s\t%s\n", lbl, file, line, $0
          }' >> "$OUT" || true
  done
}

# carbs_target_g  — целое слово
search "carbs_target_g" '\bcarbs_target_g\b'

# meal_plan — но НЕ meal_plan_type (его исключаем, т.к. это уже целевое имя)
# grep -P для отрицательного lookahead.
for r in "${ROOTS[@]}"; do
  grep -rPn "${EXCLUDES[@]}" '\bmeal_plan\b(?!_type)' "$r" 2>/dev/null \
    | awk -F: '
        {
          file=$1; line=$2; $1=""; $2=""; sub(/^::/,"");
          gsub(/\t/," ", $0);
          printf "meal_plan\t%s\t%s\t%s\n", file, line, $0
        }' >> "$OUT" || true
done

# meal_plan_type — для информации (вдруг уже где-то используется)
search "meal_plan_type" '\bmeal_plan_type\b'

# Отдельно — миграции (на них наложим только информационную метку)
for r in "${ROOTS[@]}"; do
  if [[ -d "$r" ]]; then
    while IFS= read -r mf; do
      grep -En '\bcarbs_target_g\b|\bmeal_plan\b' "$mf" 2>/dev/null \
        | awk -v f="$mf" -F: '
            {
              line=$1; $1=""; sub(/^:/,"");
              gsub(/\t/," ", $0);
              printf "MIGRATION\t%s\t%s\t%s\n", f, line, $0
            }' >> "$OUT" || true
    done < <(find "$r" -type d -name migrations -print0 | xargs -0 -I{} find {} -type f -name '*.py')
  fi
done

# Сводка
echo
echo "=== Сводка (field / count) ==="
awk -F'\t' 'NR>1 {c[$1]++} END {for(k in c) printf "  %-20s %d\n", k, c[k]}' "$OUT" \
  | sort

echo
echo "=== Файлы по полю carbs_target_g ==="
awk -F'\t' 'NR>1 && $1=="carbs_target_g" {print $2}' "$OUT" | sort -u

echo
echo "=== Файлы по полю meal_plan (без _type) ==="
awk -F'\t' 'NR>1 && $1=="meal_plan" {print $2}' "$OUT" | sort -u

echo
echo "=== Файлы по полю meal_plan_type (уже встречающиеся) ==="
awk -F'\t' 'NR>1 && $1=="meal_plan_type" {print $2}' "$OUT" | sort -u

echo
echo "Полный отчёт: $OUT"
