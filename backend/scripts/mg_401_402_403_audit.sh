#!/usr/bin/env bash
# Аудит MG-401 / MG-402 / MG-403: проверка соответствия фронта (web) и бэка ТЗ.
# Запускать на сервере: bash /opt/menugen/backend/scripts/mg_401_402_403_audit.sh

set -uo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
BACKEND="/opt/menugen/backend"
COMPOSE="/opt/menugen/docker-compose.yml"

PASS=0
FAIL=0

ok()    { echo "  ✅ $*"; PASS=$((PASS+1)); }
fail()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); }
info()  { echo "  ℹ️  $*"; }
hdr()   { echo; echo "=== $* ==="; }

check_file()    { [ -f "$1" ] && ok "файл существует: $1" || fail "НЕТ файла: $1"; }
check_grep()    { local pat="$1" file="$2" desc="$3"
                  grep -qE "$pat" "$file" 2>/dev/null && ok "$desc" || fail "$desc"; }
check_no_grep() { local pat="$1" file="$2" desc="$3"
                  ! grep -qE "$pat" "$file" 2>/dev/null && ok "$desc" || fail "$desc"; }

# ─────────────────────────────────────────────────────────────────────────────
hdr "0. Окружение"
[ -d "$WEB" ]     && ok "WEB дир есть: $WEB"     || { fail "НЕТ $WEB"; exit 1; }
[ -d "$BACKEND" ] && ok "BACKEND дир есть: $BACKEND" || fail "НЕТ $BACKEND"
[ -f "$COMPOSE" ] && ok "compose есть: $COMPOSE"     || fail "НЕТ compose"

# ─────────────────────────────────────────────────────────────────────────────
hdr "MG-401 — UI меню по компонентам"

T_TYPES="$SRC/types/index.ts"
T_MENU="$SRC/pages/Menu/MenuPage.tsx"

check_file "$T_TYPES"
check_file "$T_MENU"

echo
echo "[1.1] types/index.ts: ComponentRole / COMPONENT_ROLE_* / MealSlot"
check_grep "export type ComponentRole" "$T_TYPES" "ComponentRole тип"
check_grep "export type MealSlot"      "$T_TYPES" "MealSlot тип"
check_grep "COMPONENT_ROLE_LABELS"     "$T_TYPES" "COMPONENT_ROLE_LABELS"
check_grep "COMPONENT_ROLE_ICONS"      "$T_TYPES" "COMPONENT_ROLE_ICONS"

echo
echo "[1.2] MenuItem: component_role + meal_slot, без is_salad"
check_grep "component_role"   "$T_TYPES" "MenuItem.component_role"
check_grep "meal_slot"        "$T_TYPES" "MenuItem.meal_slot"
check_no_grep "is_salad"      "$T_TYPES" "is_salad удалён из types"

echo
echo "[1.3] MenuPage.tsx: компоненты, группировка, иконки"
check_grep "MealCard"               "$T_MENU" "MealCard компонент"
check_grep "MealDetailModal"        "$T_MENU" "MealDetailModal компонент"
check_grep "ROLE_ORDER"             "$T_MENU" "ROLE_ORDER (сортировка)"
check_grep "MEAL_SLOTS_3"           "$T_MENU" "MEAL_SLOTS_3"
check_grep "MEAL_SLOTS_5"           "$T_MENU" "MEAL_SLOTS_5"
check_grep "MEAL_SLOT_LABEL"        "$T_MENU" "MEAL_SLOT_LABEL"
check_grep "getSlotKey"             "$T_MENU" "getSlotKey helper"
check_grep "slotToMealType"         "$T_MENU" "slotToMealType helper"
check_grep "sortByRole"             "$T_MENU" "sortByRole helper"
check_grep "COMPONENT_ROLE_ICONS"   "$T_MENU" "иконки ролей в MenuPage"
check_grep "COMPONENT_ROLE_LABELS"  "$T_MENU" "лейблы ролей в MenuPage"
check_grep "hasTwoSnacks"           "$T_MENU" "детект 3 vs 5 приёмов"
check_no_grep "is_salad"            "$T_MENU" "is_salad удалён из MenuPage"

# ─────────────────────────────────────────────────────────────────────────────
hdr "MG-402 — фильтрация замены по food_group"

T_VIEWS="$BACKEND/apps/menu/views.py"
check_file "$T_VIEWS"

echo
echo "[2.1] backend: запрет swap на чужой food_group"
check_grep "MG-402"                  "$T_VIEWS" "маркер MG-402 в views.py"
check_grep "food_group"              "$T_VIEWS" "food_group упомянут"
check_grep 'другой группы|original_fg' "$T_VIEWS" "проверка food_group в swap"

echo
echo "[2.2] frontend: SwapInline с food_group"
check_grep "SwapInline"              "$T_MENU" "SwapInline компонент"
check_grep "foodGroup"               "$T_MENU" "проп foodGroup"
check_grep "food_group"              "$T_MENU" "передача food_group в API"
check_grep "swapMenuItem"            "$T_MENU" "swapMenuItem импортирован"

T_MENU_API="$SRC/api/menu.ts"
check_file "$T_MENU_API"
check_grep "swapMenuItem|MG-402"     "$T_MENU_API" "swapMenuItem в api/menu.ts"

# ─────────────────────────────────────────────────────────────────────────────
hdr "MG-403 — DayNutritionSummary"

T_DNS="$SRC/components/menu/DayNutritionSummary.tsx"
check_file "$T_DNS"

if [ -f "$T_DNS" ]; then
  echo
  echo "[3.1] DayNutritionSummary: импорты и логика"
  check_grep "items:.*MenuItem"                "$T_DNS" "принимает items"
  check_grep "targets:.*NutritionTargets"      "$T_DNS" "принимает targets"
  check_grep "calories|proteins|fats|carbs"    "$T_DNS" "суммирует КБЖУ"
  check_grep "fiber"                           "$T_DNS" "учитывает клетчатку"
fi

echo
echo "[3.2] MenuPage встраивает DayNutritionSummary"
check_grep "DayNutritionSummary"     "$T_MENU" "DayNutritionSummary импорт/использование"
check_grep "NutritionTargets"        "$T_MENU" "NutritionTargets тип"

# ─────────────────────────────────────────────────────────────────────────────
hdr "Backend smoke: реальное меню"

CONT="$(docker compose -f "$COMPOSE" ps -q web 2>/dev/null | head -1)"
if [ -z "$CONT" ]; then
  CONT="$(docker compose -f "$COMPOSE" ps -q backend 2>/dev/null | head -1)"
fi

if [ -n "$CONT" ]; then
  ok "найден backend контейнер: $CONT"

  echo
  echo "[4.1] миграция component_role применена?"
  MIGR=$(docker exec "$CONT" python manage.py showmigrations menu 2>/dev/null | grep component_role || true)
  if echo "$MIGR" | grep -q '\[X\]'; then
    ok "миграция menu/0006_component_role применена"
  else
    fail "миграция component_role НЕ применена: $MIGR"
  fi

  echo
  echo "[4.2] раскладка component_role у последнего меню"
  docker exec "$CONT" python manage.py shell -c "
from apps.menu.models import Menu, MenuItem
from collections import Counter
m = Menu.objects.order_by('-id').first()
if not m:
    print('NO_MENU')
else:
    items = MenuItem.objects.filter(menu=m)
    print(f'menu_id={m.id} items={items.count()}')
    print('by component_role:', dict(Counter(items.values_list('component_role', flat=True))))
    print('by meal_slot:',      dict(Counter(items.values_list('meal_slot', flat=True))))
    null_role = items.filter(component_role__in=['', None]).count()
    other_role = items.filter(component_role='other').count()
    print(f'null_role={null_role} other_role={other_role}')
" 2>&1 | sed 's/^/    /'

  echo
  echo "[4.3] swap-проверка food_group в views"
  docker exec "$CONT" grep -n "MG-402\|food_group" /app/apps/menu/views.py 2>/dev/null \
    | head -10 | sed 's/^/    /' || true
else
  fail "backend контейнер не найден через docker compose"
fi

# ─────────────────────────────────────────────────────────────────────────────
hdr "TypeScript: компиляция фронта"

if [ -d "$WEB/node_modules" ]; then
  cd "$WEB"
  echo "запуск: npx tsc --noEmit (только проверка типов)"
  if npx --no-install tsc --noEmit 2>&1 | tee /tmp/mg_401_audit_tsc.log | tail -30; then
    if [ -s /tmp/mg_401_audit_tsc.log ]; then
      ERRS=$(grep -c "error TS" /tmp/mg_401_audit_tsc.log || true)
      if [ "$ERRS" -eq 0 ]; then
        ok "tsc: 0 ошибок"
      else
        fail "tsc: $ERRS ошибок (см. /tmp/mg_401_audit_tsc.log)"
      fi
    else
      ok "tsc: 0 ошибок"
    fi
  else
    fail "tsc упал"
  fi
else
  info "node_modules нет — tsc пропущен"
fi

# ─────────────────────────────────────────────────────────────────────────────
hdr "Итог"
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] && echo "  → MG-401, MG-402, MG-403 закрыты ✅" || echo "  → есть пробелы, требуется доработка"
