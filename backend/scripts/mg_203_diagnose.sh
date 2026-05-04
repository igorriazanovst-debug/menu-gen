#!/usr/bin/env bash
# MG-203 diagnose — read-only.
# Цель: проверить, что API возвращает все поля КБЖУ + meal_plan_type
# и что в family-сериализаторах нет старых имён.
#
# 1) дамп apps/users/serializers.py
# 2) дамп apps/family/serializers.py + grep по family/ на старые имена
# 3) поиск всех serializers.py в проекте на 'carbs_target_g'/'meal_plan'(не _type)/'three'/'five'
# 4) поиск URL для /users/me
# 5) реальный вызов GET /users/me через django test client (raw response)

set -euo pipefail

ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg203_diagnose_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "MG-203 DIAGNOSE  ($TS)"
echo "=========================================="

# ------------------------------------------------------------
echo
echo "--- [1] apps/users/serializers.py (full dump) ---"
USR_SER="$ROOT/backend/apps/users/serializers.py"
if [ -f "$USR_SER" ]; then
  echo "FILE: $USR_SER  ($(wc -l < "$USR_SER") lines)"
  cat -n "$USR_SER"
else
  echo "MISSING: $USR_SER"
fi

# ------------------------------------------------------------
echo
echo "--- [2] apps/family/ inventory ---"
FAM_DIR="$ROOT/backend/apps/family"
if [ -d "$FAM_DIR" ]; then
  ls -la "$FAM_DIR"
  echo
  FAM_SER="$FAM_DIR/serializers.py"
  if [ -f "$FAM_SER" ]; then
    echo "FILE: $FAM_SER  ($(wc -l < "$FAM_SER") lines)"
    cat -n "$FAM_SER"
  else
    echo "(no serializers.py in family)"
  fi
  echo
  echo "  -- family/models.py (head 80 lines) --"
  if [ -f "$FAM_DIR/models.py" ]; then
    head -80 "$FAM_DIR/models.py" | nl
  fi
else
  echo "ABSENT: $FAM_DIR"
fi

# ------------------------------------------------------------
echo
echo "--- [3] grep old names in backend/apps/ ---"
cd "$ROOT/backend"
echo "  (a) carbs_target_g (со 's' — старое имя):"
grep -rn 'carbs_target_g' --include='*.py' apps/ || echo "  (none) ✅"
echo
echo "  (b) 'meal_plan' (без _type, отдельным словом):"
grep -rnE "\bmeal_plan\b" --include='*.py' apps/ \
  | grep -vE 'meal_plan_type' \
  | grep -vE '^\s*#' \
  || echo "  (none) ✅"
echo
echo "  (c) литералы 'three'/'five' (старые значения MealPlan):"
grep -rnE "['\"](three|five)['\"]" --include='*.py' apps/ || echo "  (none) ✅"

# ------------------------------------------------------------
echo
echo "--- [4] /users/me endpoint locator ---"
echo "  (a) urls files in apps/users:"
find apps/users -name 'urls*.py' -exec echo {} \; -exec cat -n {} \;
echo
echo "  (b) views.py users:"
USR_VIEWS="$ROOT/backend/apps/users/views.py"
if [ -f "$USR_VIEWS" ]; then
  echo "FILE: $USR_VIEWS  ($(wc -l < "$USR_VIEWS") lines)"
  cat -n "$USR_VIEWS"
fi
echo
echo "  (c) main urls.py — путь к users:"
find . -maxdepth 3 -name 'urls.py' -exec grep -l 'users' {} \; 2>/dev/null | while read f; do
  echo "  --- $f ---"
  grep -nE "users|me|profile" "$f" | head -20
done

# ------------------------------------------------------------
echo
echo "--- [5] live serializer test for pid=1 ---"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
import json
from apps.users.models import Profile
from apps.users.serializers import ProfileSerializer

p = Profile.objects.get(pk=1)
data = ProfileSerializer(p).data
print('--- ProfileSerializer output for pid=1 ---')
print(json.dumps(dict(data), ensure_ascii=False, indent=2, default=str))

# Проверка наличия ключей
required = ['calorie_target','protein_target_g','fat_target_g','carb_target_g','fiber_target_g','meal_plan_type']
missing = [k for k in required if k not in data]
extra_old = [k for k in ['carbs_target_g','meal_plan'] if k in data]
print()
print('REQUIRED present? ', 'YES ✅' if not missing else f'MISSING: {missing}')
print('OLD names absent? ', 'YES ✅' if not extra_old else f'STILL PRESENT: {extra_old}')
PYEOF

# ------------------------------------------------------------
echo
echo "--- [6] family serializers grep for nutrition fields ---"
if [ -d "$FAM_DIR" ]; then
  grep -rnE 'calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|meal_plan|carbs_target_g' \
    --include='*.py' "$FAM_DIR" || echo "  (no nutrition refs in family/) — возможно, family вообще не отдаёт КБЖУ"
fi

echo
echo "=========================================="
echo "DONE. Report saved to: $OUT"
echo "=========================================="
