#!/usr/bin/env bash
# patch_menu_redesign_apply.sh
# Раскладывает файлы из ./drop_menu_redesign/ в /opt/menugen/mobile/menugen_app/
# по структуре проекта. С бэкапами.
#
# Расположение скрипта: /opt/menugen/backend/scripts/patch_menu_redesign_apply.sh
# Расположение drop:    /opt/menugen/backend/scripts/drop_menu_redesign/
#                          ├── lib/features/menu/screens/menu_screen.dart
#                          ├── lib/features/menu/widgets/menu_day_strip.dart
#                          ├── lib/features/menu/widgets/menu_meal_carousel.dart
#                          ├── lib/features/recipes/screens/recipe_detail_screen.dart
#                          ├── lib/core/router/app_router.dart
#                          └── test/menu_screen_meal_logic_test.dart

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
MOBILE="${ROOT}/mobile/menugen_app"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DROP="${SCRIPT_DIR}/drop_menu_redesign"
TS=$(date +%Y%m%d_%H%M%S)
BAK="${ROOT}/backups/menu_redesign_${TS}"
mkdir -p "$BAK"

if [ ! -d "$DROP" ]; then
  echo "ERROR: нет директории $DROP" >&2
  echo "Положи рядом со скриптом папку drop_menu_redesign/ из ZIP." >&2
  exit 1
fi

echo "========================================================================"
echo "PATCH MENU REDESIGN — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  drop:    $DROP"
echo "  target:  $MOBILE"
echo "  backup:  $BAK"
echo "========================================================================"

# Список относительных путей (drop → mobile/menugen_app)
FILES=(
  "lib/features/menu/screens/menu_screen.dart"
  "lib/features/menu/widgets/menu_day_strip.dart"
  "lib/features/menu/widgets/menu_meal_carousel.dart"
  "lib/features/recipes/screens/recipe_detail_screen.dart"
  "lib/core/router/app_router.dart"
  "test/menu_screen_meal_logic_test.dart"
)

# Проверки наличия исходников
for f in "${FILES[@]}"; do
  if [ ! -f "${DROP}/${f}" ]; then
    echo "ERROR: нет ${DROP}/${f}" >&2
    exit 1
  fi
done

# Бэкап существующих файлов
echo
echo "→ Бэкап существующих файлов"
for f in "${FILES[@]}"; do
  src="${MOBILE}/${f}"
  if [ -f "$src" ]; then
    dst="${BAK}/${f}"
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "  backup: $f"
  else
    echo "  (новый): $f"
  fi
done

# Копирование
echo
echo "→ Копирование новых файлов"
for f in "${FILES[@]}"; do
  src="${DROP}/${f}"
  dst="${MOBILE}/${f}"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "  ok: $f"
done

echo
echo "→ Проверка зависимостей в pubspec.yaml"
PUB="${MOBILE}/pubspec.yaml"
for pkg in flutter_bloc go_router intl cached_network_image equatable; do
  if grep -qE "^\s*${pkg}:" "$PUB"; then
    echo "  ok: $pkg"
  else
    echo "  MISSING: $pkg  ← добавь в pubspec.yaml" >&2
  fi
done

echo
echo "→ Поиск Drift/old artefacts (не должно быть)"
grep -rn "MenuScreen(" "${MOBILE}/lib" 2>/dev/null | grep -v "screens/menu_screen.dart" || true

echo
echo "========================================================================"
echo "DONE."
echo "Следующие шаги:"
echo "  1. cd ${MOBILE} && flutter pub get   (если ставил flutter локально)"
echo "  2. git status / git diff в /opt/menugen"
echo "  3. CI прогон через push в ветку"
echo "  Откат: cp -r ${BAK}/lib ${MOBILE}/   (и test/)"
echo "========================================================================"
