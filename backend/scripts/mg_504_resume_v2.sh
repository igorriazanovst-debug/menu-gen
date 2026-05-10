#!/usr/bin/env bash
# MG-504 resume: продолжение после поднятия контейнеров
set -euo pipefail

ROOT="${ROOT:-/opt/menugen}"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.yml}"
TS=$(date +%Y%m%d_%H%M%S)

echo "=== MG-504 RESUME ==="

# Проверка что контейнер web запущен
if ! docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | grep -q '^backend$'; then
  echo "FAIL: контейнер web не запущен. Сначала: docker compose -f $COMPOSE_FILE up -d"
  exit 1
fi
echo "web is running"
echo

# --- DB dump (теперь когда контейнер поднят) ---
DB_BACKUP="/opt/menugen/backups/db_mg504_${TS}.sql.gz"
mkdir -p "$(dirname "$DB_BACKUP")"
echo "DB dump → $DB_BACKUP"
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U menugen menugen | gzip > "$DB_BACKUP"
echo "  size: $(du -h "$DB_BACKUP" | cut -f1)"
echo

# --- Migration ---
echo "Generate migration"
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py makemigrations users --name mg_504_profile_cheat_meal
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
echo

# --- Frontend types ---
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

# --- Tests ---
echo "Create tests apps/users/tests/test_mg_504.py"
mkdir -p "$BACKEND/apps/users/tests"
[[ -f "$BACKEND/apps/users/tests/__init__.py" ]] || touch "$BACKEND/apps/users/tests/__init__.py"
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

# --- Run tests ---
echo "Run tests"
docker compose -f "$COMPOSE_FILE" exec -T backend pytest apps/users/tests/test_mg_504.py -v
echo

echo "=== MG-504 RESUME DONE ==="
