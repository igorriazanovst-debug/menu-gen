#!/usr/bin/env bash
# MG-504 фикс users/serializers.py: правильное закрытие Meta.fields кортежа
set -eu

ROOT="/opt/menugen"
F="$ROOT/backend/apps/users/serializers.py"
TS=$(date +%Y%m%d_%H%M%S)
BAK="/tmp/users_serializers_${TS}.bak"

echo "=== MG-504 users/serializers.py FIX ==="
cp "$F" "$BAK"
echo "Backup → $BAK"
echo

python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/users/serializers.py")
src = p.read_text(encoding="utf-8")

# Битый паттерн (как в family до фикса):
#  "targets_meta",
#      , "bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date")
# Заменяем на:
#  "targets_meta",
#  ) + MG504_FIELDS
broken_pattern = re.compile(
    r'("targets_meta",\s*\n)\s*,\s*"bedtime_hour"\s*,\s*"cheat_meal_interval"\s*,\s*"last_cheat_meal_date"\s*\)',
)
m = broken_pattern.search(src)
if not m:
    raise SystemExit("ERROR: битый паттерн не найден")

src = broken_pattern.sub(r'\1        ) + MG504_FIELDS', src)
p.write_text(src, encoding="utf-8")
print("  Meta.fields: ') + MG504_FIELDS' restored")
PYEOF

echo
echo "=== Контекст (140-150) ==="
sed -n '120,150p' "$F" | cat -n
echo

echo "=== Python syntax check ==="
docker compose -f "$ROOT/docker-compose.yml" exec -T backend python -c \
  "import ast; ast.parse(open('apps/users/serializers.py').read()); print('  users/serializers OK')"
echo

echo "=== Импорт-тест ==="
docker compose -f "$ROOT/docker-compose.yml" exec -T backend python -c \
  "from apps.users.serializers import ProfileSerializer; print('  users.ProfileSerializer.Meta.fields:'); [print('   ', f) for f in ProfileSerializer.Meta.fields]"

echo
echo "=== DONE ==="
