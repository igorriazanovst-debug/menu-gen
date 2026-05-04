#!/usr/bin/env bash
# MG-202 APPLY:
#   - бэкап БД (gzip) + бэкап файлов
#   - переписать apps/users/nutrition.py под формулы бэклога MG-202
#   - добавить Profile.save() override в apps/users/models.py
#   - убрать дубликат расчёта в apps/users/signals.py (если был)
#   - пересчитать pid=1 c force=True
# Идемпотентен (по маркеру MG_202_V=1 в файлах).

set -euo pipefail

ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups"
mkdir -p "$BAK"

NUTR="$ROOT/backend/apps/users/nutrition.py"
MODELS="$ROOT/backend/apps/users/models.py"
SIGNALS="$ROOT/backend/apps/users/signals.py"

LOG="/tmp/mg202_apply_${TS}.log"
exec > >(tee "$LOG") 2>&1

echo "=========================================="
echo "MG-202 APPLY  ($TS)"
echo "=========================================="

# ------------------------------------------------------------
# [0] PRE-CHECK: file presence + idempotency marker
# ------------------------------------------------------------
for f in "$NUTR" "$MODELS" "$SIGNALS"; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done

if grep -q 'MG_202_V *= *1' "$NUTR" 2>/dev/null; then
  echo "[idempotency] $NUTR already has MG_202_V=1 — apply already done."
  echo "If you want to re-run, remove the marker line first."
  echo "Showing current state:"
  grep -n 'MG_202_V' "$NUTR" || true
  exit 0
fi

# ------------------------------------------------------------
# [1] BACKUPS
# ------------------------------------------------------------
echo
echo "--- [1] BACKUPS ---"
DB_DUMP="$BAK/before_mg202_${TS}.sql.gz"
echo "  pg_dump -> $DB_DUMP"
docker compose -f "$COMPOSE" exec -T db \
  pg_dump -U menugen_user -d menugen --no-owner --no-acl | gzip > "$DB_DUMP"
ls -la "$DB_DUMP"

NUTR_BAK="$BAK/nutrition.py.bak_mg202_${TS}"
MODELS_BAK="$BAK/models.py.bak_mg202_${TS}"
SIGNALS_BAK="$BAK/signals.py.bak_mg202_${TS}"
cp "$NUTR"    "$NUTR_BAK"
cp "$MODELS"  "$MODELS_BAK"
cp "$SIGNALS" "$SIGNALS_BAK"
echo "  files backed up:"
ls -la "$NUTR_BAK" "$MODELS_BAK" "$SIGNALS_BAK"

# ------------------------------------------------------------
# [2] REWRITE apps/users/nutrition.py
# ------------------------------------------------------------
echo
echo "--- [2] rewrite apps/users/nutrition.py (MG-202 formulas) ---"
cat > "$NUTR" <<'PYEOF'
"""
Расчёт целевых КБЖУ по формулам Mifflin-St Jeor (MG-202).

Алгоритм:
  1) BMR (базовый метаболизм) = Mifflin-St Jeor
        male:   10*w + 6.25*h - 5*age + 5
        female: 10*w + 6.25*h - 5*age - 161
        other:  10*w + 6.25*h - 5*age - 78  (среднее)
  2) TDEE = BMR * activity_factor
  3) Целевые калории по цели:
        lose_weight: TDEE - 500
        gain_weight: TDEE + 300
        maintain / healthy: TDEE
  4) Макросы:
        белок:    1.5 г/кг веса
        жир:      30% калорий / 9
        углеводы: (calories - белки*4 - жиры*9) / 4
        клетчатка: 14 г / 1000 ккал
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

MG_202_V = 1   # маркер версии формулы (для идемпотентности apply-скрипта)

ACTIVITY_FACTOR = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}

GOAL_DELTA_KCAL = {
    "lose_weight": -500,
    "gain_weight": +300,
    "maintain":       0,
    "healthy":        0,
}

PROTEIN_PER_KG = 1.5
FAT_PCT_OF_CAL = 0.30
FIBER_PER_1000_KCAL = 14


def mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "male":
        return base + 5
    if gender == "female":
        return base - 161
    return base - 78


def tdee(bmr: float, activity_level: str) -> float:
    return bmr * ACTIVITY_FACTOR.get(activity_level, 1.55)


def calorie_target_for_goal(tdee_value: float, goal: str) -> int:
    delta = GOAL_DELTA_KCAL.get(goal, 0)
    return int(round(tdee_value + delta))


def macro_targets(calories: int, weight_kg: float) -> dict:
    """{protein_g, fat_g, carbs_g, fiber_g} по формуле MG-202."""
    protein_g = round(weight_kg * PROTEIN_PER_KG, 1)
    fat_g     = round((calories * FAT_PCT_OF_CAL) / 9, 1)
    cal_protein = protein_g * 4
    cal_fat     = fat_g * 9
    cal_carbs   = max(0, calories - cal_protein - cal_fat)
    carbs_g     = round(cal_carbs / 4, 1)
    fiber_g     = round(calories / 1000 * FIBER_PER_1000_KCAL, 1)
    return {
        "protein_g": protein_g,
        "fat_g":     fat_g,
        "carbs_g":   carbs_g,
        "fiber_g":   fiber_g,
    }


def _age_from_birth_year(birth_year: int | None) -> int | None:
    if not birth_year:
        return None
    return date.today().year - birth_year


def calculate_targets(profile) -> dict | None:
    """
    На вход — Profile instance. Возвращает dict с целями или None,
    если данных недостаточно.
    """
    if not profile.weight_kg or not profile.height_cm:
        return None
    age = _age_from_birth_year(profile.birth_year)
    if age is None:
        return None
    gender = (profile.gender or "other").lower()

    weight = float(profile.weight_kg)
    height = float(profile.height_cm)

    bmr      = mifflin_st_jeor(weight, height, age, gender)
    tdee_val = tdee(bmr, (profile.activity_level or "moderate"))
    cals     = calorie_target_for_goal(tdee_val, (profile.goal or "maintain"))
    macros   = macro_targets(cals, weight)

    return {
        "calorie_target":   cals,
        "protein_target_g": Decimal(str(macros["protein_g"])),
        "fat_target_g":     Decimal(str(macros["fat_g"])),
        "carb_target_g":    Decimal(str(macros["carbs_g"])),
        "fiber_target_g":   Decimal(str(macros["fiber_g"])),
    }


def fill_profile_targets(profile, force: bool = False) -> bool:
    """
    Заполняет цели в профиле. Не перезаписывает заданные пользователем
    значения (если force=False).
    Возвращает True если что-то изменилось.
    """
    targets = calculate_targets(profile)
    if not targets:
        return False
    changed = False
    for field, value in targets.items():
        current = getattr(profile, field, None)
        if force or current is None:
            if current != value:
                setattr(profile, field, value)
                changed = True
    return changed
PYEOF

echo "  -> wrote $NUTR ($(wc -l < "$NUTR") lines)"

# ------------------------------------------------------------
# [3] Add Profile.save() override + remove signals dup
# ------------------------------------------------------------
echo
echo "--- [3] models.py + signals.py edits ---"

python3 <<PYEOF
from pathlib import Path

models = Path("$MODELS").read_text(encoding="utf-8")
signals = Path("$SIGNALS").read_text(encoding="utf-8")

# === models.py: добавить Profile.save() override ===
MARK = "# MG-202: auto-fill targets on save"
if MARK in models:
    print("  models.py: marker already present, skip")
else:
    # Найти класс Profile и добавить save() в конец класса.
    # Стратегия: ищем "class Profile(", дальше дописываем save() аккуратно
    # перед концом класса (по отступам).
    lines = models.splitlines(keepends=True)
    out = []
    in_profile = False
    profile_indent = None
    inserted = False

    def make_save_block(indent: str) -> str:
        body_ind = indent + "    "
        return (
f'''
{indent}# MG-202: auto-fill targets on save
{indent}def save(self, *args, **kwargs):
{body_ind}from .nutrition import fill_profile_targets
{body_ind}# заполняем цели только если не заполнены вручную (force=False)
{body_ind}fill_profile_targets(self, force=False)
{body_ind}super().save(*args, **kwargs)
'''
        )

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not in_profile:
            out.append(line)
            if stripped.startswith("class Profile(") or stripped.startswith("class Profile:"):
                in_profile = True
                profile_indent = line[: len(line) - len(stripped)]
            continue
        # внутри класса Profile: ждём строку, которая на уровне класса (или меньше) не пустая
        # — т.е. начало следующего top-level класса/функции; туда вставим save()
        if stripped == "":
            out.append(line)
            continue
        cur_indent = line[: len(line) - len(stripped)]
        if len(cur_indent) <= len(profile_indent) and not inserted:
            # вышли из класса -> вставить save() ПЕРЕД этой строкой
            out.append(make_save_block(profile_indent + "    "))
            inserted = True
            in_profile = False
        out.append(line)

    if in_profile and not inserted:
        # класс Profile — последний в файле, дописываем в конец
        if not out[-1].endswith("\n"):
            out.append("\n")
        out.append(make_save_block(profile_indent + "    "))
        inserted = True

    if inserted:
        Path("$MODELS").write_text("".join(out), encoding="utf-8")
        print("  models.py: Profile.save() inserted")
    else:
        print("  models.py: ERROR — class Profile not found")
        raise SystemExit(2)

# === signals.py: отключить дубликат (если post_save -> fill_profile_targets) ===
SIG_MARK = "# MG-202: signal disabled"
if SIG_MARK in signals:
    print("  signals.py: marker already present, skip")
else:
    src = signals
    # Стратегия: закомментировать вызов fill_profile_targets и его save() внутри signal-функции,
    # т.к. теперь это делает Profile.save(). Сам файл не удаляем.
    # Идём грубо: оборачиваем тело функции, использующей fill_profile_targets, в "no-op".
    if "fill_profile_targets" in src:
        new_src = src.replace(
            "fill_profile_targets",
            "# MG-202: signal disabled — handled in Profile.save() now\n    # fill_profile_targets"
        )
        # ещё раз — чтобы не задвоить:
        Path("$SIGNALS").write_text(new_src, encoding="utf-8")
        print("  signals.py: fill_profile_targets call commented out")
    else:
        print("  signals.py: no fill_profile_targets call found, nothing to do")
PYEOF

echo
echo "  --- Profile class (head) after edit ---"
awk '/^class Profile\b/{flag=1} flag{print NR": "$0; if(/def save\(/){c++}; if(c && /super\(\).save/){print "    [end save block]"; exit}}' "$MODELS" || true

echo
echo "  --- signals.py head ---"
sed -n '1,40p' "$SIGNALS"

# ------------------------------------------------------------
# [4] Recalculate pid=1 with force=True
# ------------------------------------------------------------
echo
echo "--- [4] recalc pid=1 (force=True) ---"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.models import Profile
from apps.users.nutrition import fill_profile_targets

p = Profile.objects.get(pk=1)
print('BEFORE:',
      'cal=', p.calorie_target,
      'P=',   p.protein_target_g,
      'F=',   p.fat_target_g,
      'C=',   p.carb_target_g,
      'Fb=',  p.fiber_target_g)

changed = fill_profile_targets(p, force=True)
p.save()
p.refresh_from_db()

print('AFTER :',
      'cal=', p.calorie_target,
      'P=',   p.protein_target_g,
      'F=',   p.fat_target_g,
      'C=',   p.carb_target_g,
      'Fb=',  p.fiber_target_g)
print('changed=', changed)
PYEOF

# ------------------------------------------------------------
# [5] Final sanity
# ------------------------------------------------------------
echo
echo "--- [5] final sanity ---"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.nutrition import MG_202_V, calculate_targets
from apps.users.models import Profile
print('MG_202_V =', MG_202_V)

# Базовый юнит-тест на эталонные значения для pid=1:
#   male, 41 y.o., 178 cm, 75 kg, moderate, lose_weight
#   BMR  = 10*75 + 6.25*178 - 5*41 + 5 = 1662.5
#   TDEE = 1662.5 * 1.55                = 2576.875
#   cal  = 2576.875 - 500                = 2076.875 -> 2077
#   P    = 1.5*75                        = 112.5
#   F    = 2077*0.3/9                    ≈ 69.2
#   C    = (2077 - 112.5*4 - 69.2*9)/4   ≈ 251.0
p = Profile.objects.get(pk=1)
t = calculate_targets(p)
print('expected cal≈2077, got', t['calorie_target'])
print('expected P  =112.5, got', t['protein_target_g'])
print('expected F  ≈69.2,  got', t['fat_target_g'])
print('expected C  ≈251.0, got', t['carb_target_g'])
PYEOF

# ------------------------------------------------------------
# [6] Rollback hint
# ------------------------------------------------------------
cat <<EOF

==========================================
DONE. Log: $LOG

ROLLBACK COMMANDS (if needed):
  # 1) restore files
  cp "$NUTR_BAK"    "$NUTR"
  cp "$MODELS_BAK"  "$MODELS"
  cp "$SIGNALS_BAK" "$SIGNALS"

  # 2) restore DB
  gunzip -c "$DB_DUMP" | \\
    docker compose -f "$COMPOSE" exec -T db psql -U menugen_user -d menugen
==========================================
EOF
