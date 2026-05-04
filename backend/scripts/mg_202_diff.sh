#!/usr/bin/env bash
# MG-202 diff — read-only.
# Считает по НОВОЙ формуле (бэклог MG-202) и показывает diff vs DB
# для всех профилей. БД не модифицирует.

set -euo pipefail

ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/mg202_diff_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "MG-202 DIFF (current DB vs MG-202 formula)"
echo "TS: $TS"
echo "=========================================="

docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.models import Profile
from datetime import date
from decimal import Decimal

ACT = {
    'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
    'active': 1.725, 'very_active': 1.9,
}

def calc_new(p):
    """Формула из бэклога MG-202 + клетчатка 14г/1000ккал."""
    if not p.weight_kg or not p.height_cm or not p.birth_year:
        return None
    age = date.today().year - p.birth_year
    w = float(p.weight_kg)
    h = float(p.height_cm)
    g = (p.gender or 'other').lower()
    if g == 'male':
        bmr = 10*w + 6.25*h - 5*age + 5
    elif g == 'female':
        bmr = 10*w + 6.25*h - 5*age - 161
    else:
        bmr = 10*w + 6.25*h - 5*age - 78
    tdee = bmr * ACT.get((p.activity_level or 'moderate'), 1.55)
    goal = (p.goal or 'maintain').lower()
    if goal == 'lose_weight':
        cal = tdee - 500
    elif goal == 'gain_weight':
        cal = tdee + 300
    else:  # maintain / healthy
        cal = tdee
    cal = int(round(cal))
    protein_g = round(1.5 * w, 1)
    fat_g     = round((cal * 0.30) / 9, 1)
    carb_g    = round((cal - protein_g*4 - fat_g*9) / 4, 1)
    fiber_g   = round(cal / 1000 * 14, 1)
    return {
        'calorie_target':   cal,
        'protein_target_g': protein_g,
        'fat_target_g':     fat_g,
        'carb_target_g':    carb_g,
        'fiber_target_g':   fiber_g,
        'bmr':              round(bmr, 1),
        'tdee':             round(tdee, 1),
        'age':              age,
    }

def fmt(v):
    if v is None:
        return 'None'
    return str(v)

profiles = Profile.objects.all().order_by('id')
total = profiles.count()
print(f'Total profiles: {total}\n')

if total == 0:
    print('Нет профилей в БД.')
    raise SystemExit

for p in profiles:
    print(f'--- pid={p.id}  user_id={p.user_id} ---')
    print(f'  inputs: gender={p.gender}  birth_year={p.birth_year}  '
          f'h={p.height_cm}  w={p.weight_kg}  '
          f'activity={p.activity_level}  goal={p.goal}  meal_plan_type={p.meal_plan_type}')
    n = calc_new(p)
    if n is None:
        print('  [skip] недостаточно данных для расчёта (нужны weight_kg, height_cm, birth_year)')
        print()
        continue
    print(f'  age={n["age"]}  BMR={n["bmr"]}  TDEE={n["tdee"]}')
    print()
    fields = [
        ('calorie_target',   p.calorie_target,   n['calorie_target']),
        ('protein_target_g', p.protein_target_g, n['protein_target_g']),
        ('fat_target_g',     p.fat_target_g,     n['fat_target_g']),
        ('carb_target_g',    p.carb_target_g,    n['carb_target_g']),
        ('fiber_target_g',   p.fiber_target_g,   n['fiber_target_g']),
    ]
    print(f'  {"field":<20}  {"current":>10}  {"new":>10}  {"diff":>10}')
    for name, cur, new in fields:
        try:
            d = float(new) - float(cur) if cur is not None else None
            d_str = f'{d:+.1f}' if d is not None else '   (None)'
        except Exception:
            d_str = '   ?'
        marker = '' if cur is not None and abs(float(new) - float(cur)) < 0.05 else '  <-- CHANGE'
        print(f'  {name:<20}  {fmt(cur):>10}  {fmt(new):>10}  {d_str:>10}{marker}')
    print()

print('=== SUMMARY ===')
print(f'Profiles total: {total}')
print('Если все CHANGE-строки приемлемы — apply пересчитает только эти поля.')
PYEOF

echo
echo "Report saved to: $OUT"
