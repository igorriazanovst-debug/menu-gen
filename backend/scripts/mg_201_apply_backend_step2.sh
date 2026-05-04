#!/usr/bin/env bash
# MG-201 STEP 2 — заменить старые имена в backend-коде:
#   carbs_target_g -> carb_target_g
#   meal_plan      -> meal_plan_type   (ТОЛЬКО как whole word и НЕ перед '_type')
#
# Файлы:
#   /opt/menugen/backend/apps/users/serializers.py
#   /opt/menugen/backend/apps/users/nutrition.py
#
# Идемпотентность: до правки делаем .bak; после правки проверяем,
# что старые имена не остались (кроме комментариев — которых там нет).
#
# Откат: cp <FILE>.bak <FILE>

set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$ROOT/backups"
mkdir -p "$BACKUP_DIR"

FILES=(
  "$ROOT/backend/apps/users/serializers.py"
  "$ROOT/backend/apps/users/nutrition.py"
)

echo "================================================================"
echo "MG-201 STEP 2 — backend code rename (serializers.py, nutrition.py)"
echo "================================================================"

# Python-патчер: правим целыми словами через regex
patch_file() {
  local f="$1"
  local backup="$BACKUP_DIR/$(basename "$f").bak_mg201_${TS}"
  cp "$f" "$backup"
  echo
  echo ">>> $f"
  echo "    backup: $backup"

  python3 - "$f" <<'PYEOF'
import re, sys
path = sys.argv[1]
src = open(path, encoding='utf-8').read()
orig = src

# carbs_target_g -> carb_target_g (whole word)
src = re.sub(r'\bcarbs_target_g\b', 'carb_target_g', src)

# meal_plan -> meal_plan_type
# но НЕ если уже meal_plan_type (negative lookahead)
src = re.sub(r'\bmeal_plan\b(?!_type)', 'meal_plan_type', src)

if src != orig:
    open(path, 'w', encoding='utf-8').write(src)
    # подсчитаем заменённое
    n_carb = orig.count('carbs_target_g') - src.count('carbs_target_g')
    n_meal = (len(re.findall(r'\bmeal_plan\b(?!_type)', orig))
              - len(re.findall(r'\bmeal_plan\b(?!_type)', src)))
    print(f'    заменено: carbs_target_g={n_carb}, meal_plan(без _type)={n_meal}')
else:
    print('    ничего не изменилось (уже актуально)')
PYEOF

  # Контроль: остатки старых имён
  if grep -nE '\bcarbs_target_g\b' "$f" >/dev/null; then
    echo "    [!] осталось упоминание carbs_target_g — откат"
    cp "$backup" "$f"
    return 1
  fi
  if grep -nPE '\bmeal_plan\b(?!_type)' "$f" >/dev/null 2>&1 \
     || grep -nE '\bmeal_plan[^_]' "$f" | grep -v '^#' >/dev/null; then
    # перепроверим строго через python
    leftover=$(python3 - "$f" <<'PYEOF'
import re, sys
src = open(sys.argv[1], encoding='utf-8').read()
hits = re.findall(r'\bmeal_plan\b(?!_type)', src)
print(len(hits))
PYEOF
)
    if [[ "$leftover" -ne 0 ]]; then
      echo "    [!] осталось $leftover упоминаний meal_plan (без _type) — откат"
      cp "$backup" "$f"
      return 1
    fi
  fi
  echo "    OK"
}

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "  [skip] нет файла: $f"
    continue
  fi
  patch_file "$f"
done

# Smoke-test: Django проверит синтаксис и совместимость с ORM
echo
echo "[smoke] manage.py check..."
docker compose -f "$COMPOSE" exec -T backend python manage.py check

echo
echo "[smoke] обращение к Profile через ORM..."
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.users.models import Profile
from apps.users.serializers import *  # noqa  — проверяем, что серилизаторы импортируются
from apps.users import nutrition       # noqa  — проверяем nutrition.py
p = Profile.objects.first()
if p:
    print('  pid:', p.id)
    print('  carb_target_g:', p.carb_target_g)
    print('  meal_plan_type:', p.meal_plan_type)
else:
    print('  (нет записей)')
print('  модули users.serializers и users.nutrition импортируются: OK')
"

echo
echo "================================================================"
echo "MG-201 STEP 2 ГОТОВО."
echo "Откат файлов:"
for f in "${FILES[@]}"; do
  bak=$(ls -t "$BACKUP_DIR"/$(basename "$f").bak_mg201_* 2>/dev/null | head -1 || true)
  [[ -n "$bak" ]] && echo "  cp $bak $f"
done
echo "================================================================"
