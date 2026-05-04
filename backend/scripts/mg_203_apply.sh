#!/usr/bin/env bash
# MG-203 APPLY:
#   - бэкап apps/family/serializers.py
#   - в family.ProfileSerializer добавить protein/fat/carb/fiber_target_g + meal_plan_type (read_only)
#   - в family.ProfileUpdateSerializer добавить те же поля (write, allow_null)
#   - sanity: serializer-тест на pid=1 (FamilyMember pid=1)
# Идемпотентен по маркеру MG_203_V=1.

set -euo pipefail

ROOT=/opt/menugen
COMPOSE="$ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups"
mkdir -p "$BAK"

FAM_SER="$ROOT/backend/apps/family/serializers.py"
LOG="/tmp/mg203_apply_${TS}.log"
exec > >(tee "$LOG") 2>&1

echo "=========================================="
echo "MG-203 APPLY  ($TS)"
echo "=========================================="

[ -f "$FAM_SER" ] || { echo "MISSING: $FAM_SER"; exit 1; }

# ---- idempotency
if grep -q 'MG_203_V *= *1' "$FAM_SER"; then
  echo "[idempotency] $FAM_SER already has MG_203_V=1 — apply already done."
  grep -n 'MG_203_V' "$FAM_SER" || true
  exit 0
fi

# ---- backup
FAM_BAK="$BAK/family_serializers.py.bak_mg203_${TS}"
cp "$FAM_SER" "$FAM_BAK"
echo "[1] backup: $FAM_BAK"

# ---- patch
echo
echo "[2] patching family/serializers.py …"

python3 <<PYEOF
from pathlib import Path
p = Path("$FAM_SER")
src = p.read_text(encoding="utf-8")

# === ProfileSerializer (read) ===
# Найти блок класса ProfileSerializer и вставить новые поля ПОСЛЕ calorie_target.
old_read = """class ProfileSerializer(serializers.Serializer):
    birth_year = serializers.IntegerField(read_only=True)
    gender = serializers.CharField(read_only=True)
    height_cm = serializers.IntegerField(read_only=True)
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    activity_level = serializers.CharField(read_only=True)
    goal = serializers.CharField(read_only=True)
    calorie_target = serializers.IntegerField(read_only=True)"""

new_read = """class ProfileSerializer(serializers.Serializer):
    # MG_203_V = 1
    birth_year = serializers.IntegerField(read_only=True)
    gender = serializers.CharField(read_only=True)
    height_cm = serializers.IntegerField(read_only=True)
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    activity_level = serializers.CharField(read_only=True)
    goal = serializers.CharField(read_only=True)
    calorie_target = serializers.IntegerField(read_only=True)
    # MG-203: targets + meal plan
    protein_target_g = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    fat_target_g     = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    carb_target_g    = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    fiber_target_g   = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    meal_plan_type   = serializers.CharField(read_only=True)"""

if old_read not in src:
    print("ERROR: old ProfileSerializer block not found verbatim — aborting.")
    raise SystemExit(2)
src = src.replace(old_read, new_read, 1)

# === ProfileUpdateSerializer (write) ===
# Добавить поля БЖУ + meal_plan_type перед закрытием класса.
# Закрытие — ровно перед строкой "class FamilyMemberUpdateSerializer".
marker_before = "class FamilyMemberUpdateSerializer("
old_update_tail = """    calorie_target = serializers.IntegerField(required=False, allow_null=True)


""" + marker_before

new_update_tail = """    calorie_target = serializers.IntegerField(required=False, allow_null=True)
    # MG-203: targets + meal plan (write)
    protein_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    fat_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    carb_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    fiber_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    meal_plan_type = serializers.ChoiceField(
        choices=["3", "5"], required=False, allow_null=True
    )


""" + marker_before

if old_update_tail not in src:
    print("ERROR: old ProfileUpdateSerializer tail not found verbatim — aborting.")
    raise SystemExit(3)
src = src.replace(old_update_tail, new_update_tail, 1)

p.write_text(src, encoding="utf-8")
print("  patched OK")
PYEOF

echo
echo "[3] verify file syntax (py_compile)"
docker compose -f "$COMPOSE" exec -T backend python -c \
  "import py_compile; py_compile.compile('/app/apps/family/serializers.py', doraise=True); print('compile OK')"

echo
echo "[4] grep new fields in family/serializers.py"
grep -nE 'protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|MG_203_V' "$FAM_SER"

echo
echo "[5] live serializer test for FamilyMember(user_id=4) on pid=1"
docker compose -f "$COMPOSE" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
import json
from apps.family.models import FamilyMember
from apps.family.serializers import FamilyMemberSerializer

# Найти FamilyMember для пользователя из pid=1 (user_id=4)
fm = FamilyMember.objects.filter(user_id=4).first()
if not fm:
    print("FamilyMember(user_id=4) not found")
else:
    data = FamilyMemberSerializer(fm).data
    print('--- FamilyMemberSerializer for user_id=4 ---')
    print(json.dumps(dict(data), ensure_ascii=False, indent=2, default=str))
    profile = data.get('profile') or {}
    required = ['calorie_target','protein_target_g','fat_target_g',
                'carb_target_g','fiber_target_g','meal_plan_type']
    missing = [k for k in required if k not in profile]
    print()
    print('REQUIRED in family.profile? ', 'YES ✅' if not missing else f'MISSING: {missing}')
PYEOF

echo
echo "[6] Django system check"
docker compose -f "$COMPOSE" exec -T backend python manage.py check

cat <<EOF

==========================================
DONE. Log: $LOG

ROLLBACK:
  cp "$FAM_BAK" "$FAM_SER"
==========================================
EOF
