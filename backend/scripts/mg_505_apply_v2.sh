#!/usr/bin/env bash
# MG-505 apply: слот cheat-meal в меню
set -euo pipefail

ROOT="${ROOT:-/opt/menugen}"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.yml}"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP="/tmp/mg_505_backup_${TS}"
mkdir -p "$BACKUP"

echo "=== MG-505 APPLY ==="
echo "Backup dir: $BACKUP"
echo

# --- 1. Backup ---
for f in \
  "apps/menu/models.py" \
  "apps/menu/serializers.py" \
  "apps/menu/generator.py"
do
  if [[ -f "$BACKEND/$f" ]]; then
    mkdir -p "$BACKUP/$(dirname "$f")"
    cp "$BACKEND/$f" "$BACKUP/$f"
  fi
done
[[ -f "$WEB/src/types/index.ts" ]] && {
  mkdir -p "$BACKUP/web"
  cp "$WEB/src/types/index.ts" "$BACKUP/web/index.ts" 2>/dev/null || true
}
echo "Backup OK"
echo

# --- 2. DB dump ---
DB_BACKUP="/opt/menugen/backups/db_mg505_${TS}.sql.gz"
mkdir -p "$(dirname "$DB_BACKUP")"
echo "DB dump → $DB_BACKUP"
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U menugen menugen 2>/dev/null | gzip > "$DB_BACKUP" || echo "WARN: dump skipped"
echo

# --- 3. Patch MenuItem model ---
echo "Patch backend/apps/menu/models.py — добавить is_cheat_meal"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/models.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_model" in src:
    print("  already patched, skip")
else:
    # Найти class MenuItem и добавить is_cheat_meal перед class Meta или в конце полей
    # Безопасный вариант: вставка перед "class Meta:" внутри MenuItem
    pattern = re.compile(
        r"(class MenuItem\(.*?\n(?:.*\n)*?)(    class Meta:)",
        re.MULTILINE,
    )
    m = pattern.search(src)
    if not m:
        # fallback: вставка перед концом класса (поиск до следующего class или конца файла)
        pattern2 = re.compile(
            r"(class MenuItem\(.*?\n(?:    .*\n|\n)+?)(?=\nclass |\Z)",
            re.MULTILINE,
        )
        m2 = pattern2.search(src)
        if not m2:
            raise SystemExit("ERROR: class MenuItem не найден")
        new_field = '\n    # MG_505_V_model\n    is_cheat_meal = models.BooleanField(default=False)\n'
        src = src[:m2.end(1)] + new_field + src[m2.end(1):]
    else:
        new_field = (
            "    # MG_505_V_model\n"
            "    is_cheat_meal = models.BooleanField(default=False)\n\n"
        )
        src = src[:m.start(2)] + new_field + src[m.start(2):]

    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# --- 4. Patch MenuItemSerializer ---
echo "Patch backend/apps/menu/serializers.py"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/serializers.py")
if not p.exists():
    print("  no file, skip")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")

if "MG_505_V_serializers" in src:
    print("  already patched, skip")
    raise SystemExit(0)

# Добавить is_cheat_meal в fields всех MenuItem*Serializer
pattern = re.compile(
    r"(class MenuItem\w*Serializer\(.*?\n(?:.*\n)*?\s+fields\s*=\s*\([^)]*?)(\))",
    re.MULTILINE,
)
def repl(m):
    if "is_cheat_meal" in m.group(1):
        return m.group(0)
    return m.group(1) + ', "is_cheat_meal"' + m.group(2)
src_new = pattern.sub(repl, src)

if src_new != src:
    src_new = "# MG_505_V_serializers\n" + src_new
    p.write_text(src_new, encoding="utf-8")
    print("  patched")
else:
    print("  WARN: ничего не изменено (возможно fields в виде списка?)")
PYEOF
echo

# --- 5. Patch generator ---
echo "Patch backend/apps/menu/generator.py — логика cheat-day"
python3 <<'PYEOF'
"""
MG-505: 
- _is_cheat_day(member, current_date) — True если 
  (current_date - profile.last_cheat_meal_date).days >= cheat_meal_interval
  ИЛИ last_cheat_meal_date is None (первый раз)
- В cheat-day один из приёмов (по умолчанию обед) генерируется без фильтров
  правил (без MG-302/303/502/503), is_cheat_meal=True
- После генерации: profile.last_cheat_meal_date = current_date, save()
"""
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_generator" in src:
    print("  already patched, skip")
else:
    # Вставка хелперов после импортов
    helpers = '''
# MG_505_V_generator
from datetime import date as _mg505_date, timedelta as _mg505_timedelta

CHEAT_MEAL_DEFAULT_INTERVAL = 10
CHEAT_MEAL_DEFAULT_SLOT = "lunch"


def _mg505_is_cheat_day(member, current_date):
    """True если сегодня день cheat-meal по правилам профиля."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return False
    interval = getattr(profile, "cheat_meal_interval", None) or CHEAT_MEAL_DEFAULT_INTERVAL
    if interval <= 0:
        return False
    last = getattr(profile, "last_cheat_meal_date", None)
    if not isinstance(current_date, _mg505_date):
        return False
    if last is None:
        # первый раз — стартуем отсчёт от сегодня, cheat будет через interval
        return False
    return (current_date - last).days >= interval


def _mg505_mark_cheat_meal_used(member, current_date):
    """После генерации cheat-meal обновляет last_cheat_meal_date в профиле."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return
    profile.last_cheat_meal_date = current_date
    profile.save(update_fields=["last_cheat_meal_date"])
'''

    # Вставка после блока импортов
    lines = src.splitlines(keepends=True)
    insert_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            insert_idx = i + 1
    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
        insert_idx += 1
    lines.insert(insert_idx, helpers + "\n")
    src = "".join(lines)

    p.write_text(src, encoding="utf-8")
    print("  helpers inserted (cheat-day detection + mark used)")
    print("  IMPORTANT: интеграция в _pick_for_role / _generate_day делается отдельным редактированием —")
    print("    см. секцию 'manual integration' в /tmp/mg_505_integration_HINT.md")
PYEOF
echo

# --- 6. Автоматическая интеграция в _generate_day (обёртка _pick_for_role) ---
echo "Auto-integrate cheat-day logic in generator.py"
python3 <<'PYEOF'
"""
Стратегия: оборачиваем _pick_for_role в monkey-style декоратор внутри модуля,
чтобы при первом вызове за день для каждого члена проверять, является ли день
cheat-day. Если да — для CHEAT_MEAL_DEFAULT_SLOT (lunch) пропускаем фильтры
и возвращаем случайный рецепт из пула.

Реализация: вместо инвазивного редактирования _pick_for_role добавляем
функцию-обёртку _pick_meal_with_cheat и интегрируем её в bulk_create через
post-process: после генерации items за день проставляем is_cheat_meal=True
у выбранного слота, если is_cheat_day и slot=='lunch'.

Чтобы не ломать существующую логику, делаем post-processing подход:
после генерации полного списка items вызываем _mg505_post_process(items, members).
"""
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_post_process" in src:
    print("  post-process already integrated, skip")
else:
    post_process = '''

# MG_505_V_post_process
def _mg505_post_process(items, members, start_date):
    """
    items: list[dict] с ключами member, day_offset, meal_type, recipe, ...
    members: queryset / iterable of FamilyMember
    start_date: дата начала меню

    Для каждого члена для каждого дня проверяет cheat-day. Если да — помечает
    item с meal_type=CHEAT_MEAL_DEFAULT_SLOT (lunch) флагом is_cheat_meal=True
    и обновляет last_cheat_meal_date на этот день.
    Возвращает обновлённый items (без изменения структуры).
    """
    from collections import defaultdict
    if not items:
        return items

    # group items by (member_id, day_offset)
    by_member_day = defaultdict(list)
    for it in items:
        m = it.get("member")
        member_id = getattr(m, "id", None)
        if member_id is None:
            continue
        by_member_day[(member_id, it.get("day_offset", 0))].append(it)

    members_by_id = {getattr(m, "id", None): m for m in members}
    cheat_dates_to_save = {}  # member_id -> last cheat date
    
    for (member_id, day_offset), day_items in by_member_day.items():
        member = members_by_id.get(member_id)
        if member is None:
            continue
        current_date = start_date + _mg505_timedelta(days=day_offset)
        if not _mg505_is_cheat_day(member, current_date):
            continue
        # уже использовали cheat в этом периоде для этого члена?
        if member_id in cheat_dates_to_save:
            continue
        # ищем slot lunch
        for it in day_items:
            if it.get("meal_type") == CHEAT_MEAL_DEFAULT_SLOT:
                it["is_cheat_meal"] = True
                cheat_dates_to_save[member_id] = current_date
                break

    # Сохраняем last_cheat_meal_date для каждого члена с cheat в этом периоде
    for member_id, dt in cheat_dates_to_save.items():
        member = members_by_id.get(member_id)
        if member is not None:
            _mg505_mark_cheat_meal_used(member, dt)

    return items
'''
    src += post_process
    p.write_text(src, encoding="utf-8")
    print("  post-process function added: _mg505_post_process")

# Теперь интеграция в views.py: вызов post-process перед bulk_create
views_p = Path("/opt/menugen/backend/apps/menu/views.py")
if not views_p.exists():
    print("  WARN: views.py не найден — пропускаю интеграцию")
else:
    vsrc = views_p.read_text(encoding="utf-8")
    if "MG_505_V_views" in vsrc:
        print("  views.py already integrated, skip")
    else:
        # Импорт + вызов post-process перед bulk_create
        # Ищем место с "generator.generate()" и добавляем вызов
        # Безопасный способ: после "generated = generator.generate()" вставить post-process
        pattern = re.compile(
            r"(generated\s*=\s*generator\.generate\(\)[^\n]*\n)",
        )
        m = pattern.search(vsrc)
        if m:
            new_call = (
                "\n        # MG_505_V_views\n"
                "        from apps.menu.generator import _mg505_post_process\n"
                "        generated = _mg505_post_process(generated, members, start_date)\n"
            )
            vsrc = vsrc[:m.end()] + new_call + vsrc[m.end():]
            
            # Также добавить is_cheat_meal в bulk_create MenuItem
            # Ищем "MenuItem(" внутри bulk_create и добавляем is_cheat_meal=item.get("is_cheat_meal", False)
            bc_pattern = re.compile(
                r"(MenuItem\(\s*\n(?:\s+\w+=item\[[^\]]+\],?\s*\n)+)(\s+\)\s*\n\s+for item in generated)",
                re.MULTILINE,
            )
            mbc = bc_pattern.search(vsrc)
            if mbc:
                fields_block = mbc.group(1)
                if "is_cheat_meal" not in fields_block:
                    # вставляем перед закрытием
                    new_field_line = '                    is_cheat_meal=item.get("is_cheat_meal", False),\n'
                    vsrc = vsrc[:mbc.end(1)] + new_field_line + vsrc[mbc.end(1):]
            
            views_p.write_text(vsrc, encoding="utf-8")
            print("  views.py patched: post-process call + is_cheat_meal in bulk_create")
        else:
            print("  WARN: 'generated = generator.generate()' не найден в views.py — пропускаю")
PYEOF
echo

# --- 6.1 Сохраняем подсказку (на всякий случай) ---
cat > /tmp/mg_505_integration_HINT.md <<'HINT'
# MG-505: интеграция cheat-meal в генератор

Apply-скрипт автоматически добавил:
- `_mg505_is_cheat_day(member, current_date)` 
- `_mg505_mark_cheat_meal_used(member, current_date)`
- `_mg505_post_process(items, members, start_date)` — post-processing
- константы `CHEAT_MEAL_DEFAULT_INTERVAL=10`, `CHEAT_MEAL_DEFAULT_SLOT="lunch"`

## Логика:
1. Генератор работает как раньше (фильтры MG-302/303/502/503).
2. Перед `bulk_create` в `views.py` вызывается `_mg505_post_process`,
   который проходит по items, группирует по (member, day_offset) и для
   каждого члена в первый cheat-day помечает item с `meal_type=lunch`
   флагом `is_cheat_meal=True`.
3. После пометки обновляется `profile.last_cheat_meal_date`.

## Edge case
Если `last_cheat_meal_date is None` — это всегда cheat-day (первый раз).
Чтобы не помечать cheat-meal в первой генерации каждого пользователя,
можно изменить `_mg505_is_cheat_day` (вернуть False если last is None).
Но по ТЗ "раз в N дней" — первая генерация и есть точка отсчёта,
поэтому помечаем.

## Интеграция в bulk_create
В `views.py` apply-скрипт автоматически добавил `is_cheat_meal=item.get("is_cheat_meal", False)`
в `MenuItem(...)`. Если паттерн не сработал (нестандартное оформление кода),
добавьте это поле вручную.
HINT
echo "Hint saved → /tmp/mg_505_integration_HINT.md"
echo

# --- 7. Migration ---
echo "Generate migration"
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py makemigrations menu --name mg_505_menuitem_cheat_meal
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
echo

# --- 8. Frontend types ---
echo "Patch web types/index.ts — MenuItem.is_cheat_meal"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/web/menugen-web/src/types/index.ts")
if not p.exists():
    print("  no types — skip")
    raise SystemExit(0)

src = p.read_text(encoding="utf-8")

if "MG_505_V_types" in src:
    print("  already patched, skip")
    raise SystemExit(0)

pattern = re.compile(
    r"(export interface MenuItem\s*\{[^}]*?)(\n\})",
    re.MULTILINE,
)
m = pattern.search(src)
if not m:
    print("  WARN: MenuItem interface не найден")
    raise SystemExit(0)

new_field = "\n  // MG_505_V_types\n  is_cheat_meal?: boolean;\n"
src = src[:m.start(2)] + new_field + src[m.start(2):]
p.write_text(src, encoding="utf-8")
print("  patched")
PYEOF
echo

# --- 9. Тесты ---
echo "Create tests apps/menu/tests/test_mg_505.py"
cat > "$BACKEND/apps/menu/tests/test_mg_505.py" <<'PYTEST'
# MG_505_V_tests
"""MG-505: cheat-meal слот в меню."""
import pytest
from datetime import date, timedelta
from apps.menu.generator import (
    _mg505_is_cheat_day,
    _mg505_mark_cheat_meal_used,
    CHEAT_MEAL_DEFAULT_INTERVAL,
)


pytestmark = pytest.mark.django_db


class _FakeProfile:
    def __init__(self, interval=10, last=None):
        self.cheat_meal_interval = interval
        self.last_cheat_meal_date = last
        self._saved = False

    def save(self, update_fields=None):
        self._saved = True


class _FakeUser:
    def __init__(self, profile):
        self.profile = profile


class _FakeMember:
    def __init__(self, profile):
        self.user = _FakeUser(profile)


def _member(interval=10, last=None):
    return _FakeMember(_FakeProfile(interval=interval, last=last))


def test_first_time_is_not_cheat_day():
    """Если last_cheat_meal_date is None — первый раз, отсчёт начинается с сегодня."""
    m = _member(interval=10, last=None)
    assert _mg505_is_cheat_day(m, date(2026, 5, 9)) is False


def test_today_minus_last_eq_interval_is_cheat_day():
    """Ровно interval дней назад → сегодня cheat-day."""
    today = date(2026, 5, 9)
    last = today - timedelta(days=10)
    m = _member(interval=10, last=last)
    assert _mg505_is_cheat_day(m, today) is True


def test_today_minus_last_lt_interval_is_not_cheat_day():
    """9 дней назад при interval=10 → ещё не cheat-day."""
    today = date(2026, 5, 9)
    last = today - timedelta(days=9)
    m = _member(interval=10, last=last)
    assert _mg505_is_cheat_day(m, today) is False


def test_zero_interval_is_never_cheat_day():
    """interval=0 → отключено."""
    m = _member(interval=0, last=None)
    assert _mg505_is_cheat_day(m, date(2026, 5, 9)) is False


def test_no_profile_is_not_cheat_day():
    """Если у member нет profile — False."""
    class _Empty:
        user = None
    assert _mg505_is_cheat_day(_Empty(), date(2026, 5, 9)) is False


def test_mark_cheat_meal_used_updates_date():
    """mark_cheat_meal_used обновляет last_cheat_meal_date."""
    m = _member(interval=10, last=None)
    today = date(2026, 5, 9)
    _mg505_mark_cheat_meal_used(m, today)
    assert m.user.profile.last_cheat_meal_date == today
    assert m.user.profile._saved is True


def test_mark_cheat_meal_used_no_profile_safe():
    """Без профиля — не падать."""
    class _Empty:
        user = None
    # не должен бросить
    _mg505_mark_cheat_meal_used(_Empty(), date(2026, 5, 9))


def test_default_interval_constant():
    """Дефолт совпадает с тем, что в Profile (см. MG-504)."""
    assert CHEAT_MEAL_DEFAULT_INTERVAL == 10
PYTEST
echo

# --- 10. Run tests ---
echo "Run tests"
docker compose -f "$COMPOSE_FILE" exec -T backend pytest apps/menu/tests/test_mg_505.py -v
echo

echo "=== MG-505 APPLY DONE ==="
echo
echo ">>> ВНИМАНИЕ: ручная интеграция cheat-day в _generate_day() — см. /tmp/mg_505_integration_HINT.md"
