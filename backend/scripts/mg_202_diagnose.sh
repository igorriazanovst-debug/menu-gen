#!/usr/bin/env bash
# MG-202 diagnose — read-only.
# Показывает:
#   1) текущий apps/users/nutrition.py (полный дамп)
#   2) есть ли apps/users/services/ и nutrition_calc.py
#   3) где импортируется apps.users.nutrition (grep)
#   4) override Profile.save() в apps/users/models.py (если есть)
#   5) текущие поля профиля pid=1 в БД
#   6) расчёт по формуле бэклога MG-202 для pid=1 (что должно получиться)
# Результат — в /tmp/mg202_diagnose_<TS>.txt (плюс stdout).

set -euo pipefail

ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg202_diagnose_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "MG-202 DIAGNOSE  ($TS)"
echo "=========================================="

echo
echo "--- [1] FULL DUMP: apps/users/nutrition.py ---"
NUTR="$ROOT/backend/apps/users/nutrition.py"
if [ -f "$NUTR" ]; then
  echo "FILE: $NUTR"
  echo "SIZE: $(wc -c < "$NUTR") bytes, $(wc -l < "$NUTR") lines"
  echo "----------------------------------------"
  cat -n "$NUTR"
  echo "----------------------------------------"
else
  echo "MISSING: $NUTR"
fi

echo
echo "--- [2] services/ directory & nutrition_calc.py ---"
SERV="$ROOT/backend/apps/users/services"
if [ -d "$SERV" ]; then
  echo "EXISTS: $SERV"
  ls -la "$SERV"
else
  echo "ABSENT: $SERV (по бэклогу — это путь, заявленный в MG-202)"
fi
NCALC="$SERV/nutrition_calc.py"
if [ -f "$NCALC" ]; then
  echo "EXISTS file: $NCALC"
  cat -n "$NCALC"
else
  echo "ABSENT file: $NCALC"
fi

echo
echo "--- [3] grep: where apps.users.nutrition is imported / used ---"
cd "$ROOT/backend"
echo "  (a) imports of nutrition module:"
grep -rnE "from\s+apps\.users\.nutrition|from\s+\.nutrition|import\s+apps\.users\.nutrition" \
     --include='*.py' apps/ || echo "  (none)"
echo
echo "  (b) callers of recompute_nutrition_targets / calculate_targets / nutrition.* (any name):"
grep -rnE "recompute_nutrition_targets|calculate_targets|nutrition_calc" \
     --include='*.py' apps/ || echo "  (none)"

echo
echo "--- [4] Profile.save / models.py override check ---"
MODELS="$ROOT/backend/apps/users/models.py"
if [ -f "$MODELS" ]; then
  echo "FILE: $MODELS  ($(wc -l < "$MODELS") lines)"
  echo "  grep 'def save' / 'class Profile':"
  grep -nE "class Profile\b|def save\(" "$MODELS" || echo "  (no matches)"
  echo "  --- Profile class body (from 'class Profile' to next 'class ' or EOF) ---"
  awk '/^class Profile\b/{flag=1} flag{print NR": "$0} flag && /^class [A-Z]/ && !/^class Profile\b/{flag=0}' "$MODELS" \
    | head -200
else
  echo "MISSING: $MODELS"
fi

echo
echo "--- [5] Current Profile pid=1 (raw fields) ---"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.models import Profile
from datetime import date
try:
    p = Profile.objects.get(pk=1)
except Profile.DoesNotExist:
    print("Profile pid=1 не найден")
else:
    print(f"id                  = {p.id}")
    print(f"user_id             = {p.user_id}")
    print(f"birth_year          = {p.birth_year}")
    print(f"gender              = {p.gender}")
    print(f"height_cm           = {p.height_cm}")
    print(f"weight_kg           = {p.weight_kg}")
    print(f"activity_level      = {p.activity_level}")
    print(f"goal                = {p.goal}")
    print(f"calorie_target      = {p.calorie_target}")
    print(f"protein_target_g    = {p.protein_target_g}")
    print(f"fat_target_g        = {p.fat_target_g}")
    print(f"carb_target_g       = {p.carb_target_g}")
    print(f"fiber_target_g      = {p.fiber_target_g}")
    print(f"meal_plan_type      = {p.meal_plan_type}")
    print(f"updated_at          = {p.updated_at}")
PYEOF

echo
echo "--- [6] EXPECTED by MG-202 backlog formula (pid=1) ---"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.models import Profile
from datetime import date
try:
    p = Profile.objects.get(pk=1)
except Profile.DoesNotExist:
    print("Profile pid=1 не найден")
    raise SystemExit

# Параметры из MG-202 (бэклог)
ACT = {
    'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
    'active': 1.725, 'very_active': 1.9,
}
def calc(p):
    age = date.today().year - (p.birth_year or 1990)
    w = float(p.weight_kg or 0)
    h = float(p.height_cm or 0)
    g = (p.gender or '').lower()
    if g == 'male':
        bmr = 10*w + 6.25*h - 5*age + 5
    elif g == 'female':
        bmr = 10*w + 6.25*h - 5*age - 161
    else:
        bmr = 10*w + 6.25*h - 5*age - 78  # среднее male/female
    tdee = bmr * ACT.get((p.activity_level or 'moderate'), 1.55)
    goal = (p.goal or 'maintain').lower()
    if goal == 'lose_weight':
        cal = tdee - 500
    elif goal == 'gain_weight':
        cal = tdee + 300
    else:  # maintain / healthy
        cal = tdee
    protein_g = 1.5 * w
    fat_g     = (cal * 0.30) / 9
    carb_g    = (cal - protein_g*4 - fat_g*9) / 4
    fiber_g   = 14 * cal / 1000  # справочно (формула из MG-201)
    return dict(age=age, bmr=round(bmr,1), tdee=round(tdee,1),
                cal=round(cal), p=round(protein_g,1),
                f=round(fat_g,1), c=round(carb_g,1),
                fi=round(fiber_g,1))
r = calc(p)
print(f"age                 = {r['age']}")
print(f"BMR                 = {r['bmr']}")
print(f"TDEE                = {r['tdee']}")
print(f"calorie_target      = {r['cal']}        (current in DB: {p.calorie_target})")
print(f"protein_target_g    = {r['p']}        (current in DB: {p.protein_target_g})")
print(f"fat_target_g        = {r['f']}        (current in DB: {p.fat_target_g})")
print(f"carb_target_g       = {r['c']}        (current in DB: {p.carb_target_g})")
print(f"fiber_target_g (14g/1000kcal, для справки) = {r['fi']}  (current in DB: {p.fiber_target_g})")
PYEOF

echo
echo "=========================================="
echo "DONE. Report saved to: $OUT"
echo "=========================================="
