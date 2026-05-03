#!/usr/bin/env bash
# MG-201 frontend APPLY: правка 3 файлов под новые имена полей Profile
set -euo pipefail

WEB_ROOT="/opt/menugen/web/menugen-web"
SRC="${WEB_ROOT}/src"
BACKUP_DIR="/opt/menugen/backups"
COMPOSE="/opt/menugen/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

F_TYPES="${SRC}/types/index.ts"
F_PROFILE="${SRC}/pages/Profile/ProfilePage.tsx"
F_MENU="${SRC}/pages/Menu/MenuPage.tsx"

mkdir -p "${BACKUP_DIR}"

echo "=== [0] Pre-flight ==="
for f in "$F_TYPES" "$F_PROFILE" "$F_MENU" "$COMPOSE"; do
  [ -f "$f" ] || { echo "ERROR: $f not found" >&2; exit 1; }
done

# идемпотентность: если все 3 файла уже не содержат старых имён — выходим
OLD_HITS=$(grep -rEn '\b(carbs_target_g|meal_plan)\b' "$F_TYPES" "$F_PROFILE" "$F_MENU" | wc -l || true)
THREE_FIVE_HITS=$(grep -rEn "['\"](three|five)['\"]" "$F_TYPES" "$F_PROFILE" "$F_MENU" | wc -l || true)
if [ "$OLD_HITS" = "0" ] && [ "$THREE_FIVE_HITS" = "0" ]; then
  echo "Уже мигрировано — старых имён и литералов 'three'/'five' нет. Выход."
  exit 0
fi
echo "  старых имён: ${OLD_HITS}, литералов 'three'/'five': ${THREE_FIVE_HITS} — продолжаю"
echo

echo "=== [1] Бэкапы ==="
cp "$F_TYPES"   "${BACKUP_DIR}/index.ts.bak_mg201fe_${TS}"
cp "$F_PROFILE" "${BACKUP_DIR}/ProfilePage.tsx.bak_mg201fe_${TS}"
cp "$F_MENU"    "${BACKUP_DIR}/MenuPage.tsx.bak_mg201fe_${TS}"
echo "  ${BACKUP_DIR}/index.ts.bak_mg201fe_${TS}"
echo "  ${BACKUP_DIR}/ProfilePage.tsx.bak_mg201fe_${TS}"
echo "  ${BACKUP_DIR}/MenuPage.tsx.bak_mg201fe_${TS}"
echo

echo "=== [2] Точечные правки через python (без хардкода путей в коде) ==="
python3 <<PYEOF
import re, sys, pathlib

F_TYPES   = pathlib.Path("${F_TYPES}")
F_PROFILE = pathlib.Path("${F_PROFILE}")
F_MENU    = pathlib.Path("${F_MENU}")

def edit(path: pathlib.Path, edits: list[tuple[str, str, str]]) -> None:
    """edits: list of (old, new, label). Каждая замена должна сработать ровно как указано."""
    src = path.read_text(encoding="utf-8")
    for old, new, label in edits:
        if old not in src:
            print(f"  [SKIP] {path.name}: '{label}' — фрагмент уже отсутствует")
            continue
        before = src.count(old)
        src = src.replace(old, new)
        print(f"  [OK]   {path.name}: '{label}' — заменено {before} вхождение(й)")
    path.write_text(src, encoding="utf-8")

# ── types/index.ts ──────────────────────────────────────────────────────────
edit(F_TYPES, [
    ("export type MealPlan = 'three' | 'five';",
     "export type MealPlan = '3' | '5';",
     "MealPlan literal '3'|'5'"),
    ("  carbs_target_g:   string;",
     "  carb_target_g:    string;",
     "NutritionTargets.carb_target_g"),
    ("  carbs_target_g?:   string | null;",
     "  carb_target_g?:    string | null;",
     "UserProfile.carb_target_g"),
    ("  meal_plan?: MealPlan;",
     "  meal_plan_type?: MealPlan;",
     "UserProfile.meal_plan_type"),
])

# ── ProfilePage.tsx ─────────────────────────────────────────────────────────
edit(F_PROFILE, [
    ("  { value: 'three', label: '3 приёма', hint: 'завтрак / обед / ужин' },",
     "  { value: '3', label: '3 приёма', hint: 'завтрак / обед / ужин' },",
     "MEAL_PLAN_OPTIONS[0].value"),
    ("  { value: 'five',  label: '5 приёмов', hint: '+ перекусы между ними' },",
     "  { value: '5', label: '5 приёмов', hint: '+ перекусы между ними' },",
     "MEAL_PLAN_OPTIONS[1].value"),
    ("  const [mealPlan, setMealPlan] = useState<MealPlan>(user?.profile?.meal_plan ?? 'three');",
     "  const [mealPlan, setMealPlan] = useState<MealPlan>(user?.profile?.meal_plan_type ?? '3');",
     "useState mealPlan default"),
    ("    setMealPlan(user?.profile?.meal_plan ?? 'three');",
     "    setMealPlan(user?.profile?.meal_plan_type ?? '3');",
     "useEffect setMealPlan default"),
    ("  }, [user?.id, user?.name, user?.profile?.meal_plan]);",
     "  }, [user?.id, user?.name, user?.profile?.meal_plan_type]);",
     "useEffect deps"),
    ("        carbs_target_g:   String(p.carbs_target_g ?? ''),",
     "        carb_target_g:    String(p.carb_target_g ?? ''),",
     "targets.carb_target_g"),
    ("      const payload: Partial<UserProfile> = { meal_plan: mealPlan };",
     "      const payload: Partial<UserProfile> = { meal_plan_type: mealPlan };",
     "payload meal_plan_type"),
    ("          {/* meal_plan — план приёмов пищи */}",
     "          {/* meal_plan_type — план приёмов пищи */}",
     "comment meal_plan_type"),
    ('            <MacroPill label="Углев" value={num(targets.carbs_target_g)}    unit="г"    color="bg-emerald-50 text-emerald-700" />',
     '            <MacroPill label="Углев" value={num(targets.carb_target_g)}     unit="г"    color="bg-emerald-50 text-emerald-700" />',
     "MacroPill carb_target_g"),
])

# ── MenuPage.tsx ────────────────────────────────────────────────────────────
edit(F_MENU, [
    ("    ((user?.profile as any)?.meal_plan === 'five') ? '5' : '3'",
     "    (user?.profile?.meal_plan_type ?? '3')",
     "remove 'five' costyl"),
])

print("ОК — правки внесены")
PYEOF
echo

echo "=== [3] Пост-проверка: остатки старых имён ==="
LEFT_OLD=$(grep -rEn '\b(carbs_target_g|meal_plan)\b' "$F_TYPES" "$F_PROFILE" "$F_MENU" || true)
LEFT_THREE_FIVE=$(grep -rEn "['\"](three|five)['\"]" "$F_TYPES" "$F_PROFILE" "$F_MENU" || true)
if [ -z "$LEFT_OLD" ] && [ -z "$LEFT_THREE_FIVE" ]; then
  echo "  ✅ старых имён и литералов нет"
else
  echo "  ⚠️ ОСТАЛИСЬ:"
  [ -n "$LEFT_OLD" ] && echo "$LEFT_OLD"
  [ -n "$LEFT_THREE_FIVE" ] && echo "$LEFT_THREE_FIVE"
fi
echo

echo "=== [4] Подтверждаем новые имена ==="
grep -rEn '\b(carb_target_g|meal_plan_type)\b' "$F_TYPES" "$F_PROFILE" "$F_MENU" || echo "  (не найдено — это плохо)"
echo

echo "=== [5] tsc --noEmit через docker compose ==="
SERVICE=""
for s in web frontend menugen-web; do
  if docker compose -f "$COMPOSE" config --services 2>/dev/null | grep -qx "$s"; then
    SERVICE="$s"; break
  fi
done

if [ -z "$SERVICE" ]; then
  echo "  ⚠️ сервис web/frontend/menugen-web не найден в docker-compose.yml"
  echo "  доступные сервисы:"
  docker compose -f "$COMPOSE" config --services 2>/dev/null | sed 's/^/    /'
  echo "  → tsc пропущен. Запусти вручную:"
  echo "    docker compose -f ${COMPOSE} exec -T <web-сервис> npx tsc --noEmit"
else
  echo "  сервис: ${SERVICE}"
  if docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -c "test -d node_modules" 2>/dev/null; then
    set +e
    docker compose -f "$COMPOSE" exec -T "$SERVICE" npx --no-install tsc --noEmit
    RC=$?
    set -e
    if [ $RC -eq 0 ]; then
      echo "  ✅ tsc --noEmit прошёл"
    else
      echo "  ❌ tsc вернул код $RC — см. вывод выше"
    fi
  else
    echo "  ⚠️ node_modules в контейнере ${SERVICE} нет — tsc пропущен"
    echo "    запусти вручную после npm install"
  fi
fi
echo

echo "=== [6] Откат (если нужно) ==="
cat <<EOF
cp ${BACKUP_DIR}/index.ts.bak_mg201fe_${TS}        ${F_TYPES}
cp ${BACKUP_DIR}/ProfilePage.tsx.bak_mg201fe_${TS} ${F_PROFILE}
cp ${BACKUP_DIR}/MenuPage.tsx.bak_mg201fe_${TS}    ${F_MENU}
EOF
echo
echo "Готово."
