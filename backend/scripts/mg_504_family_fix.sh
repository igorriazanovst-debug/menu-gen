#!/usr/bin/env bash
# MG-504 фикс: откат битого patch FamilyMemberSerializer.Meta.fields +
# правильная вставка полей в ProfileSerializer и ProfileUpdateSerializer
set -eu

ROOT="/opt/menugen"
F="$ROOT/backend/apps/family/serializers.py"
TS=$(date +%Y%m%d_%H%M%S)
BAK="/tmp/family_serializers_${TS}.bak"

echo "=== MG-504 family/serializers.py FIX ==="
cp "$F" "$BAK"
echo "Backup → $BAK"
echo

python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/family/serializers.py")
src = p.read_text(encoding="utf-8")

# 1) Откатить битую вставку в Meta.fields FamilyMemberSerializer
# Был добавлен ", "bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date")"
# в неправильное место. Найдём и вернём правильное закрытие кортежа.
broken_pattern = re.compile(
    r'\n\s*,\s*"bedtime_hour"\s*,\s*"cheat_meal_interval"\s*,\s*"last_cheat_meal_date"\s*\)',
)
m = broken_pattern.search(src)
if m:
    # перед битой строкой должна быть строка "joined_at," — заменяем на закрытие кортежа
    src = broken_pattern.sub('\n        )', src)
    print("  [1/3] removed broken FamilyMemberSerializer.Meta.fields injection")
else:
    print("  [1/3] no broken injection — skip")

# 2) Добавить MG-504 поля в ProfileSerializer (явные поля, как остальные в этом классе)
if "# MG_504_V_family_profile" in src:
    print("  [2/3] ProfileSerializer already patched — skip")
else:
    # Вставка после meal_plan_type
    pattern = re.compile(
        r"(    meal_plan_type\s*=\s*serializers\.CharField\(read_only=True\)\n)",
    )
    m = pattern.search(src)
    if not m:
        raise SystemExit("ERROR: meal_plan_type не найден в ProfileSerializer family")
    new_block = (
        "\n    # MG_504_V_family_profile\n"
        "    bedtime_hour = serializers.IntegerField(read_only=True, allow_null=True)\n"
        "    cheat_meal_interval = serializers.IntegerField(read_only=True)\n"
        "    last_cheat_meal_date = serializers.DateField(read_only=True, allow_null=True)\n"
    )
    src = src[:m.end()] + new_block + src[m.end():]
    print("  [2/3] ProfileSerializer (read) — fields added")

# 3) Добавить поля в ProfileUpdateSerializer (для записи)
if "# MG_504_V_family_update" in src:
    print("  [3/3] ProfileUpdateSerializer already patched — skip")
else:
    # Вставка перед закрывающей скобкой meal_plan_type ChoiceField
    # meal_plan_type = serializers.ChoiceField( choices=["3", "5"], required=False, allow_null=True )
    pattern = re.compile(
        r"(    meal_plan_type = serializers\.ChoiceField\(\s*\n"
        r"\s*choices=\[\"3\", \"5\"\], required=False, allow_null=True\s*\n"
        r"\s*\)\n)",
    )
    m = pattern.search(src)
    if not m:
        # fallback: попроще
        pattern = re.compile(
            r"(    meal_plan_type = serializers\.ChoiceField\([^)]*\)\n)",
        )
        m = pattern.search(src)
    if not m:
        raise SystemExit("ERROR: meal_plan_type write field не найден")
    new_block = (
        "\n    # MG_504_V_family_update\n"
        "    bedtime_hour = serializers.IntegerField(\n"
        "        required=False, allow_null=True, min_value=0, max_value=23\n"
        "    )\n"
        "    cheat_meal_interval = serializers.IntegerField(\n"
        "        required=False, min_value=1\n"
        "    )\n"
        "    last_cheat_meal_date = serializers.DateField(\n"
        "        required=False, allow_null=True\n"
        "    )\n"
    )
    src = src[:m.end()] + new_block + src[m.end():]
    print("  [3/3] ProfileUpdateSerializer (write) — fields added")

p.write_text(src, encoding="utf-8")
print("DONE")
PYEOF

echo
echo "=== Проверка синтаксиса Python ==="
docker compose -f "$ROOT/docker-compose.yml" exec -T backend python -c \
  "import ast; ast.parse(open('apps/family/serializers.py').read()); print('  syntax OK')"

echo
echo "=== Контекст (60-90) ==="
sed -n '60,95p' "$F" | cat -n

echo
echo "=== Контекст (110-160) — ProfileUpdateSerializer ==="
sed -n '110,170p' "$F" | cat -n
