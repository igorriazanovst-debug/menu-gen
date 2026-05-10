#!/usr/bin/env bash
# MG-504 resume v3: миграция + frontend types + тесты
# Использует POSTGRES_USER/POSTGRES_DB изнутри контейнера db, сервис backend (не web).
set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

echo "=== MG-504 RESUME v3 ==="

# --- 1) DB dump через env ---
DB_BACKUP="$ROOT/backups/db_mg504_${TS}.sql.gz"
mkdir -p "$(dirname "$DB_BACKUP")"
DB_USER_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_USER"')
DB_NAME_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_DB"')
echo "[1/5] DB dump (user=$DB_USER_REAL db=$DB_NAME_REAL) → $DB_BACKUP"
$COMPOSE exec -T db pg_dump -U "$DB_USER_REAL" "$DB_NAME_REAL" | gzip > "$DB_BACKUP"
echo "      size: $(du -h "$DB_BACKUP" | cut -f1)"
echo

# --- 2) Django check ---
echo "[2/5] django check"
$COMPOSE exec -T backend python manage.py check
echo

# --- 3) Migration ---
echo "[3/5] makemigrations + migrate"
$COMPOSE exec -T backend python manage.py makemigrations users --name mg_504_profile_cheat_meal
$COMPOSE exec -T backend python manage.py migrate users
echo

# --- 4) Frontend types ---
echo "[4/5] patch web types/index.ts"
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

# --- 5) Tests ---
echo "[5/5] create + run tests"
mkdir -p "$BACKEND/apps/users/tests"
[[ -f "$BACKEND/apps/users/tests/__init__.py" ]] || touch "$BACKEND/apps/users/tests/__init__.py"

cat > "$BACKEND/apps/users/tests/test_mg_504.py" <<'PYTEST'
# MG_504_V_tests
"""MG-504: поля Profile для cheat-meal и времени отхода ко сну."""
import pytest
from datetime import date
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(email="mg504@test.local", password="x")


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

echo "  тесты записаны: apps/users/tests/test_mg_504.py"
$COMPOSE exec -T backend pytest apps/users/tests/test_mg_504.py -v
echo

echo "=== MG-504 RESUME DONE ==="
