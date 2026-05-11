#!/usr/bin/env bash
# MG-605.B: миграция DiaryEntry — planned_menu_item FK + is_eaten
#
# - apps/diary/models.py: добавить planned_menu_item (FK→MenuItem, SET_NULL, unique)
#                         и is_eaten (Boolean, default=False)
# - apps/diary/migrations/0004_planned_menu_item_is_eaten.py: миграция
# - apps/diary/serializers.py: вернуть новые поля в read/write
# - регресс существующих тестов
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
DIARY="$BACKEND/apps/diary"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_605b_backup_${TS}"

mkdir -p "$BAK"
echo "[1/6] Backup → $BAK"
for f in models.py serializers.py; do
  cp -v "$DIARY/$f" "$BAK/$f"
done

# ─────────────────────────────────────────────────────────────────────────────
# [2/6] models.py — добавить поля planned_menu_item + is_eaten
# ─────────────────────────────────────────────────────────────────────────────
echo "[2/6] models.py — добавляем planned_menu_item + is_eaten"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/models.py")
src = p.read_text(encoding="utf-8")

if "MG_605B_V_models" in src:
    print("  models.py: уже пропатчен")
    raise SystemExit(0)

# 1) Импорт MenuItem
old_imports = (
    "from django.db import models\n"
    "\n"
    "from apps.family.models import FamilyMember\n"
    "from apps.recipes.models import Recipe\n"
)
new_imports = (
    "from django.db import models\n"
    "\n"
    "from apps.family.models import FamilyMember\n"
    "from apps.recipes.models import Recipe\n"
    "# MG_605B_V_models: связь дневник→меню (план-факт)\n"
    "from apps.menu.models import MenuItem\n"
)
assert old_imports in src, "ОШИБКА: не нашёл блок импортов"
src = src.replace(old_imports, new_imports, 1)

# 2) Добавить поля после quantity (перед created_at)
old_fields = (
    '    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)\n'
    '    created_at = models.DateTimeField(auto_now_add=True)\n'
)
new_fields = (
    '    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)\n'
    '    # MG_605B_V_models: план-факт\n'
    '    planned_menu_item = models.ForeignKey(\n'
    '        MenuItem,\n'
    '        on_delete=models.SET_NULL,\n'
    '        null=True,\n'
    '        blank=True,\n'
    '        unique=True,\n'
    '        related_name="diary_entries",\n'
    '    )\n'
    '    is_eaten = models.BooleanField(default=False)\n'
    '    created_at = models.DateTimeField(auto_now_add=True)\n'
)
assert old_fields in src, "ОШИБКА: не нашёл quantity+created_at в DiaryEntry"
src = src.replace(old_fields, new_fields, 1)

p.write_text(src, encoding="utf-8")
print("  models.py: пропатчен")
PYEOF

# ─────────────────────────────────────────────────────────────────────────────
# [3/6] makemigrations + проверка содержимого
# ─────────────────────────────────────────────────────────────────────────────
echo "[3/6] makemigrations diary"
$COMPOSE exec -T backend python manage.py makemigrations diary --name planned_menu_item_is_eaten 2>&1 | tail -10
echo

echo "  Новый файл миграции:"
$COMPOSE exec -T backend bash -c 'ls -la apps/diary/migrations/0004*.py 2>/dev/null'
echo
echo "  Содержимое 0004:"
$COMPOSE exec -T backend bash -c 'cat apps/diary/migrations/0004*.py 2>/dev/null'
echo

# ─────────────────────────────────────────────────────────────────────────────
# [4/6] Применить миграцию
# ─────────────────────────────────────────────────────────────────────────────
echo "[4/6] migrate diary"
$COMPOSE exec -T backend python manage.py migrate diary 2>&1 | tail -10
echo

# ─────────────────────────────────────────────────────────────────────────────
# [5/6] serializers.py — добавить поля
# ─────────────────────────────────────────────────────────────────────────────
echo "[5/6] serializers.py — добавляем planned_menu_item + is_eaten в read/write"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/serializers.py")
src = p.read_text(encoding="utf-8")

if "MG_605B_V_serializers" in src:
    print("  serializers.py: уже пропатчен")
    raise SystemExit(0)

# DiaryEntrySerializer (read): добавить planned_menu_item + is_eaten
old_read_fields = (
    '        fields = (\n'
    '            "id",\n'
    '            "date",\n'
    '            "meal_type",\n'
    '            "recipe",\n'
    '            "recipe_title",\n'
    '            "custom_name",\n'
    '            "nutrition",\n'
    '            "quantity",\n'
    '            "created_at",\n'
    '        )\n'
    '        read_only_fields = ("id", "created_at")\n'
)
new_read_fields = (
    '        fields = (\n'
    '            "id",\n'
    '            "date",\n'
    '            "meal_type",\n'
    '            "recipe",\n'
    '            "recipe_title",\n'
    '            "custom_name",\n'
    '            "nutrition",\n'
    '            "quantity",\n'
    '            "planned_menu_item",  # MG_605B_V_serializers\n'
    '            "is_eaten",  # MG_605B_V_serializers\n'
    '            "created_at",\n'
    '        )\n'
    '        read_only_fields = ("id", "created_at")\n'
)
assert old_read_fields in src, "ОШИБКА: не нашёл fields в DiaryEntrySerializer"
src = src.replace(old_read_fields, new_read_fields, 1)

# DiaryEntryWriteSerializer: добавить planned_menu_item + is_eaten
old_write_fields = (
    '        fields = ("date", "meal_type", "recipe", "custom_name", "nutrition", "quantity")\n'
)
new_write_fields = (
    '        # MG_605B_V_serializers: план-факт\n'
    '        fields = (\n'
    '            "date", "meal_type", "recipe", "custom_name",\n'
    '            "nutrition", "quantity", "planned_menu_item", "is_eaten",\n'
    '        )\n'
)
assert old_write_fields in src, "ОШИБКА: не нашёл fields в DiaryEntryWriteSerializer"
src = src.replace(old_write_fields, new_write_fields, 1)

p.write_text(src, encoding="utf-8")
print("  serializers.py: пропатчен")
PYEOF

# ─────────────────────────────────────────────────────────────────────────────
# [6/6] Проверка
# ─────────────────────────────────────────────────────────────────────────────
echo "[6/6] py_compile + django check + регресс apps/diary"
$COMPOSE exec -T backend python -m py_compile \
  apps/diary/models.py \
  apps/diary/serializers.py && echo "  py_compile OK"
echo

$COMPOSE exec -T backend python manage.py check 2>&1 | tail -5
echo

$COMPOSE exec -T backend python manage.py showmigrations diary 2>&1
echo

echo "  Проверка структуры diary_entries (новые столбцы)"
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.db import connection
cur = connection.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name='diary_entries'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:30s} {r[1]:20s} null={r[2]}")
print("---")
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint WHERE conrelid = 'diary_entries'::regclass
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")
PY
echo

echo "  Регресс apps/diary"
$COMPOSE exec -T backend pytest apps/diary/ -q --tb=short 2>&1 | tail -10
echo

echo "=== 605.B apply done. Backup: $BAK ==="
