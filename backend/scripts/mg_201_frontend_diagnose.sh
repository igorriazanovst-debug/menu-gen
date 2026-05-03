#!/usr/bin/env bash
# MG-201 frontend diagnose: показать актуальное состояние перед правкой
set -euo pipefail

WEB_ROOT="/opt/menugen/web/menugen-web"
SRC="${WEB_ROOT}/src"
OUT_DIR="/tmp"
TS=$(date +%Y%m%d_%H%M%S)
REPORT="${OUT_DIR}/mg201_frontend_diagnose_${TS}.txt"

if [ ! -d "$SRC" ]; then
  echo "ERROR: ${SRC} not found" >&2
  exit 1
fi

{
  echo "=== MG-201 FRONTEND DIAGNOSE @ ${TS} ==="
  echo "WEB_ROOT: ${WEB_ROOT}"
  echo

  echo "=== [1] grep по старым именам (carbs_target_g, meal_plan как whole-word) ==="
  grep -rEn '\b(carbs_target_g|meal_plan)\b' "${SRC}" \
    --exclude-dir=node_modules --exclude-dir=build --exclude-dir=dist \
    || echo "(не найдено)"
  echo

  echo "=== [2] grep по новым именам (carb_target_g, meal_plan_type) ==="
  grep -rEn '\b(carb_target_g|meal_plan_type)\b' "${SRC}" \
    --exclude-dir=node_modules --exclude-dir=build --exclude-dir=dist \
    || echo "(не найдено)"
  echo

  echo "=== [3] grep по литералам 'three'/'five' (костыль MealPlan) ==="
  grep -rEn "['\"](three|five)['\"]" "${SRC}" \
    --exclude-dir=node_modules --exclude-dir=build --exclude-dir=dist \
    || echo "(не найдено)"
  echo

  for f in \
    "src/types/index.ts" \
    "src/pages/Profile/ProfilePage.tsx" \
    "src/pages/Menu/MenuPage.tsx"
  do
    full="${WEB_ROOT}/${f}"
    echo "=== [FILE] ${f} ==="
    if [ -f "$full" ]; then
      echo "(size: $(wc -c < "$full") bytes, lines: $(wc -l < "$full"))"
      echo "----- BEGIN -----"
      cat -n "$full"
      echo "----- END -----"
    else
      echo "(не найден: ${full})"
    fi
    echo
  done

  echo "=== [4] package.json — есть ли скрипт typecheck/tsc ==="
  if [ -f "${WEB_ROOT}/package.json" ]; then
    grep -E '"(typecheck|tsc|build|lint)"' "${WEB_ROOT}/package.json" || echo "(скриптов typecheck/tsc/build/lint нет в package.json)"
  else
    echo "(package.json не найден)"
  fi
  echo

  echo "=== [5] tsconfig.json — есть ли strict ==="
  if [ -f "${WEB_ROOT}/tsconfig.json" ]; then
    cat "${WEB_ROOT}/tsconfig.json"
  else
    echo "(tsconfig.json не найден)"
  fi
} | tee "${REPORT}"

echo
echo "Отчёт сохранён: ${REPORT}"
