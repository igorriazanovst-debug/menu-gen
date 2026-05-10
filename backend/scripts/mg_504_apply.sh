#!/usr/bin/env bash
# MG-504 apply: bedtime_hour, cheat_meal_interval, last_cheat_meal_date в Profile
set -euo pipefail

ROOT="${ROOT:-/opt/menugen}"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.yml}"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP="/tmp/mg_504_backup_${TS}"
mkdir -p "$BACKUP"

echo "=== MG-504 APPLY ==="
echo "Backup dir: $BACKUP"
echo

# --- 1. Backup затрагиваемых файлов ---
for f in \
  "apps/users/models.py" \
  "apps/users/serializers.py" \
  "apps/family/serializers.py"
do
  if [[ -f "$BACKEND/$f" ]]; then
    mkdir -p "$BACKUP/$(dirname "$f")"
    cp "$BACKEND/$f" "$BACKUP/$f"
  fi
done
[[ -f "$WEB/src/types/index.ts" ]] && {
  mkdir -p "$BACKUP/web"
  cp "$WEB/src/types/index.ts" "$BACKUP/web/index.ts"
}
echo "Backup OK"
echo

# --- 2. Дамп БД ---
DB_BACKUP="/opt/menugen/backups/db_mg504_${TS}.sql.gz"
mkdir -p "$(dirname "$DB_BACKUP")"
echo "DB dump → $DB_BACKUP"
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U menugen menugen 2>/dev/null | gzip > "$DB_BACKUP" || echo "WARN: dump skipped"
echo

# --- 3. Patch Profile model ---
echo "Patch backend/apps/users/models.py"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/users/models.py")
src = p.read_text(encoding="utf-8")

if "MG_504_V_model" in src:
    print("  already patched, skip")
else:
    # Найти класс Profile и добавить поля перед updated_at (или в конец полей)
    # Маркер: ищем "calorie_target = " и вставляем после связанных полей
    # Безопаснее: добавить перед "updated_at = models.DateTimeField(auto_now=True)"
    new_fields = '''    # MG_504_V_model
    bedtime_hour = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Час отхода ко сну (0-23) для правила «не есть за 3ч до сна»",
    )
    cheat_meal_interval = models.PositiveSmallIntegerField(
        default=10,
        help_text="Интервал в днях между cheat-meal приёмами",
    )
    last_cheat_meal_date = models.DateField(
        null=True, blank=True,
        help_text="Дата последнего cheat-meal — обновляется генератором",
    )
'''
    # Вставка перед updated_at в Profile
    pattern = re.compile(
        r"(class Profile\(.*?\n(?:.*\n)*?)(    updated_at = models\.DateTimeField\(auto_now=True\))",
        re.MULTILINE,
    )
    m = pattern.search(src)
    if not m:
        # fallback: ищем последнее поле перед class Meta в Profile
        pattern2 = re.compile(
            r"(class Profile\(.*?\n(?:.*\n)*?)(    class Meta:)",
            re.MULTILINE,
        )
        m2 = pattern2.search(src)
        if not m2:
            raise SystemExit("ERROR: не нашёл точку вставки в Profile")
        src = src[:m2.start(2)] + new_fields + "\n" + src[m2.start(2):]
    else:
        src = src[:m.start(2)] + new_fields + src[m.start(2):]

    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# --- 4. Patch users serializers ---
echo "Patch backend/apps/users/serializers.py"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/users/serializers.py")
src = p.read_text(encoding="utf-8")

if "MG_504_V_serializers" in src:
    print("  already patched, skip")
else:
    # ProfileSerializer: добавить поля в Meta.fields
    # Маркер MG501_FIELDS уже есть — добавим аналогично MG504_FIELDS
    if "MG504_FIELDS" not in src:
        # вставить константу в начало после импортов
        # ищем первое место после импортов (после блока from ... import ...)
        lines = src.splitlines(keepends=True)
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_idx = i + 1
        # пропустить пустые строки сразу после импортов
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1
        const_block = (
            "\n# MG_504_V_serializers\n"
            'MG504_FIELDS = ("bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date")\n\n'
        )
        lines.insert(insert_idx, const_block)
        src = "".join(lines)

    # Расширить fields у всех ProfileSerializer (там, где уже есть MG501_FIELDS)
    if "MG501_FIELDS" in src and "MG504_FIELDS" in src:
        # после "+ MG501_FIELDS" добавляем "+ MG504_FIELDS"
        src = re.sub(
            r"\+ MG501_FIELDS(?!\s*\+\s*MG504_FIELDS)",
            "+ MG501_FIELDS + MG504_FIELDS",
            src,
        )
    else:
        # если MG501_FIELDS не использовался — добавить вручную в Meta.fields кортеж
        # Ищем class ProfileSerializer и его Meta.fields
        pattern = re.compile(
            r"(class ProfileSerializer\(.*?\n(?:.*\n)*?\s+fields\s*=\s*\([^)]*?)(\))",
            re.MULTILINE,
        )
        def repl(m):
            return m.group(1) + ', "bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date"' + m.group(2)
        src_new = pattern.sub(repl, src)
        if src_new != src:
            src = src_new

    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# --- 5. Patch family serializers ---
echo "Patch backend/apps/family/serializers.py"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/family/serializers.py")
if not p.exists():
    print("  no family/serializers.py — skip")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")

if "MG_504_V_family" in src:
    print("  already patched, skip")
    raise SystemExit(0)

# Если в family/serializers.py есть импорт MG501_FIELDS — используем тот же подход
if "MG501_FIELDS" in src:
    # добавить импорт MG504_FIELDS если есть импорт MG501_FIELDS
    src = re.sub(
        r"from apps\.users\.serializers import (.*?MG501_FIELDS.*?)$",
        lambda m: ("from apps.users.serializers import " + m.group(1) + ", MG504_FIELDS"
                   if "MG504_FIELDS" not in m.group(1) else m.group(0)),
        src,
        flags=re.MULTILINE,
    )
    # после "+ MG501_FIELDS" — добавить "+ MG504_FIELDS"
    src = re.sub(
        r"\+ MG501_FIELDS(?!\s*\+\s*MG504_FIELDS)",
        "+ MG501_FIELDS + MG504_FIELDS",
        src,
    )
else:
    # добавить поля напрямую в кортежи fields для всех Profile-сериализаторов
    pattern = re.compile(
        r"(class \w*Profile\w*Serializer\(.*?\n(?:.*\n)*?\s+fields\s*=\s*\([^)]*?)(\))",
        re.MULTILINE,
    )
    def repl(m):
        return m.group(1) + ', "bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date"' + m.group(2)
    src = pattern.sub(repl, src)

# маркер
src = "# MG_504_V_family\n" + src
p.write_text(src, encoding="utf-8")
print("  patched")
PYEOF
echo

# --- 6. Migration ---
echo "Generate migration"
docker compose -f "$COMPOSE_FILE" exec -T web python manage.py makemigrations users --name mg_504_profile_cheat_meal
docker compose -f "$COMPOSE_FILE" exec -T web python manage.py migrate
echo

# --- 7. Frontend types ---
echo "Patch web types/index.ts"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/web/menugen-web/src/types/index.ts")
if not p.exists():
    print("  no types/index.ts — skip")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")

if "MG_504_V_types" in src:
    print("  already patched, skip")
    raise SystemExit(0)

# Найти UserProfile (или Profile) и добавить поля
pattern = re.compile(
    r"(export interface UserProfile\s*\{[^}]*?)(\n\})",
    re.MULTILINE,
)
m = pattern.search(src)
if not m:
    pattern = re.compile(
        r"(export interface Profile\s*\{[^}]*?)(\n\})",
        re.MULTILINE,
    )
    m = pattern.search(src)

if not m:
    print("  WARN: UserProfile / Profile interface не найден — пропускаю")
    raise SystemExit(0)

new_fields = (
    "\n  // MG_504_V_types\n"
    "  bedtime_hour?: number | null;\n"
    "  cheat_meal_interval?: number;\n"
    "  last_cheat_meal_date?: string | null;\n"
)
src = src[:m.start(2)] + new_fields + src[m.start(2):]
p.write_text(src, encoding="utf-8")
print("  patched")
PYEOF
echo

# --- 8. Tests ---
echo "Create tests apps/users/tests/test_mg_504.py"
cat > "$BACKEND/apps/users/tests/test_mg_504.py" <<'PYTEST'
# MG_504_V_tests
"""MG-504: поля Profile для cheat-meal и времени отхода ко сну."""
import pytest
from datetime import date
from django.contrib.auth import get_user_model
from apps.users.models import Profile

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    u = User.objects.create_user(email="mg504@test.local", password="x")
    return u


def test_profile_has_mg_504_fields(user):
    p = user.profile
    assert hasattr(p, "bedtime_hour")
    assert hasattr(p, "cheat_meal_interval")
    assert hasattr(p, "last_cheat_meal_date")


def test_bedtime_hour_default_null(user):
    assert user.profile.bedtime_hour is None


def test_cheat_meal_interval_default_10(user):
    assert user.profile.cheat_meal_interval == 10


def test_last_cheat_meal_date_default_null(user):
    assert user.profile.last_cheat_meal_date is None


def test_set_and_save_bedtime_hour(user):
    p = user.profile
    p.bedtime_hour = 23
    p.save()
    p.refresh_from_db()
    assert p.bedtime_hour == 23


def test_set_cheat_meal_interval(user):
    p = user.profile
    p.cheat_meal_interval = 7
    p.save()
    p.refresh_from_db()
    assert p.cheat_meal_interval == 7


def test_set_last_cheat_meal_date(user):
    p = user.profile
    p.last_cheat_meal_date = date(2026, 5, 1)
    p.save()
    p.refresh_from_db()
    assert p.last_cheat_meal_date == date(2026, 5, 1)
PYTEST
echo

# --- 9. Run tests ---
echo "Run tests"
docker compose -f "$COMPOSE_FILE" exec -T web pytest apps/users/tests/test_mg_504.py -v
echo

echo "=== MG-504 APPLY DONE ==="
