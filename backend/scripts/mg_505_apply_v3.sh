#!/usr/bin/env bash
# MG-505 apply v3: cheat-meal слот в меню (гибридный подход)
# - В cheat-day для slot in {lunch, dinner} (детерминированный выбор):
#   protein-компонент выбирается БЕЗ фильтров MG-302/303/502/503.
#   Остальные компоненты — как обычно.
# - Все компоненты cheat-приёма помечаются is_cheat_meal=True.
# - После генерации: profile.last_cheat_meal_date = date генерации этого члена.
#
# Стек интеграции:
# 1) MenuItem.is_cheat_meal — миграция
# 2) MenuItemSerializer.fields += ("is_cheat_meal",)
# 3) Generator: импорт _mg505_*, флаг + bypass для cheat-protein
# 4) views.py: post-process пометка items + сохранение last_cheat_meal_date,
#               добавление is_cheat_meal в bulk_create

set -eu

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
WEB="$ROOT/web/menugen-web"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP="/tmp/mg_505_backup_${TS}"
mkdir -p "$BACKUP"

echo "=== MG-505 APPLY v3 ==="
echo "Backup: $BACKUP"
echo

# ─── 1. Backup файлов ───
for f in "apps/menu/models.py" "apps/menu/serializers.py" "apps/menu/generator.py" "apps/menu/views.py"; do
  if [[ -f "$BACKEND/$f" ]]; then
    mkdir -p "$BACKUP/$(dirname "$f")"
    cp "$BACKEND/$f" "$BACKUP/$f"
  fi
done
[[ -f "$WEB/src/types/index.ts" ]] && {
  mkdir -p "$BACKUP/web"
  cp "$WEB/src/types/index.ts" "$BACKUP/web/index.ts"
}
echo "[1/8] backup OK"
echo

# ─── 2. DB dump через .env ───
DB_BACKUP="$ROOT/backups/db_mg505_${TS}.sql.gz"
mkdir -p "$(dirname "$DB_BACKUP")"
DB_USER_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_USER"')
DB_NAME_REAL=$($COMPOSE exec -T db sh -c 'printf %s "$POSTGRES_DB"')
echo "[2/8] DB dump (user=$DB_USER_REAL db=$DB_NAME_REAL) → $DB_BACKUP"
$COMPOSE exec -T db pg_dump -U "$DB_USER_REAL" "$DB_NAME_REAL" | gzip > "$DB_BACKUP"
echo "      size: $(du -h "$DB_BACKUP" | cut -f1)"
echo

# ─── 3. MenuItem.is_cheat_meal ───
echo "[3/8] patch apps/menu/models.py — MenuItem.is_cheat_meal"
python3 <<'PYEOF'
from pathlib import Path
import re

p = Path("/opt/menugen/backend/apps/menu/models.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_model" in src:
    print("  already patched, skip")
else:
    # вставка перед "class Meta:" внутри MenuItem
    pattern = re.compile(
        r"(class MenuItem\(.*?\n(?:.*\n)*?)(    class Meta:)",
        re.MULTILINE,
    )
    m = pattern.search(src)
    if not m:
        raise SystemExit("ERROR: class MenuItem.Meta not found")
    insert = (
        "    # MG_505_V_model\n"
        "    is_cheat_meal = models.BooleanField(default=False)\n\n"
    )
    src = src[:m.start(2)] + insert + src[m.start(2):]
    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# ─── 4. MenuItemSerializer ───
echo "[4/8] patch apps/menu/serializers.py — fields += is_cheat_meal"
python3 <<'PYEOF'
from pathlib import Path
import re

p = Path("/opt/menugen/backend/apps/menu/serializers.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_serializers" in src:
    print("  already patched, skip")
else:
    # Текущее: fields = ("id", "day_offset", "meal_type", "meal_slot", "component_role", "recipe", "member_name", "quantity")
    # Цель: добавить "is_cheat_meal" перед закрывающей )
    pattern = re.compile(
        r'(class MenuItemSerializer\(.*?\n(?:.*?\n)*?\s+fields\s*=\s*\(\s*"id".*?"quantity")(\))',
        re.MULTILINE,
    )
    m = pattern.search(src)
    if not m:
        raise SystemExit("ERROR: MenuItemSerializer.Meta.fields not matched")
    src = src[:m.end(1)] + ', "is_cheat_meal"' + src[m.end(1):]
    src = "# MG_505_V_serializers\n" + src
    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# ─── 5. Generator: helpers + bypass для cheat-protein ───
echo "[5/8] patch apps/menu/generator.py — cheat-meal helpers + bypass"
python3 <<'PYEOF'
from pathlib import Path
import re

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

# 5a) helpers
if "MG_505_V_generator" in src:
    print("  helpers already inserted, skip")
else:
    helpers = '''

# MG_505_V_generator: cheat-meal слот
from datetime import date as _mg505_date, timedelta as _mg505_timedelta

CHEAT_MEAL_DEFAULT_INTERVAL = 10
CHEAT_MEAL_SLOTS = ("lunch", "dinner")  # cheat-meal случается в одном из этих слотов


def _mg505_is_cheat_day(member, current_date):
    """True если сегодня день cheat-meal по правилам профиля."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return False
    interval = getattr(profile, "cheat_meal_interval", None) or CHEAT_MEAL_DEFAULT_INTERVAL
    if interval <= 0:
        return False
    if not isinstance(current_date, _mg505_date):
        return False
    last = getattr(profile, "last_cheat_meal_date", None)
    if last is None:
        # первый раз — начинаем отсчёт от сегодня, cheat случится через interval дней
        return False
    return (current_date - last).days >= interval


def _mg505_pick_cheat_slot(member_id, day_offset):
    """Детерминированный выбор lunch/dinner для cheat-meal."""
    return CHEAT_MEAL_SLOTS[(int(member_id) + int(day_offset)) % len(CHEAT_MEAL_SLOTS)]


def _mg505_mark_cheat_meal_used(member, current_date):
    """Обновляет last_cheat_meal_date в профиле."""
    profile = getattr(getattr(member, "user", None), "profile", None)
    if profile is None:
        return
    profile.last_cheat_meal_date = current_date
    profile.save(update_fields=["last_cheat_meal_date"])
'''
    # вставка после блока импортов
    lines = src.splitlines(keepends=True)
    insert_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("from ") or s.startswith("import "):
            insert_idx = i + 1
    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
        insert_idx += 1
    lines.insert(insert_idx, helpers + "\n")
    src = "".join(lines)
    print("  helpers inserted")

# 5b) Bypass фильтров MG-302/303/502/503 для cheat-protein
# Передаём флаг is_cheat=True в _pick_for_role и пропускаем 4 фильтра
if "MG_505_V_pick_bypass" in src:
    print("  pick_for_role bypass already integrated, skip")
else:
    # добавляем параметр is_cheat=False в сигнатуру _pick_for_role
    src = re.sub(
        r"(def _pick_for_role\(\s*self,\s*\n(?:\s+\w+:\s*[^,]+,\s*\n)+\s+day_offset:\s*int,\s*\n\s*\)\s*->\s*Optional\[Recipe\]:)",
        lambda m: m.group(0).replace(
            "day_offset: int,\n    ) -> Optional[Recipe]:",
            "day_offset: int,\n        is_cheat: bool = False,  # MG_505_V_pick_bypass\n    ) -> Optional[Recipe]:"
        ),
        src,
        count=1,
    )

    # обернуть блок MG-302 (если role == "protein"): if is_cheat — пропускаем
    src = src.replace(
        '        # MG_302_V_generator: недельные/дневные лимиты — только для protein\n        if role == "protein":',
        '        # MG_302_V_generator: недельные/дневные лимиты — только для protein\n'
        '        # MG_505_V_pick_bypass: в cheat-meal не применяем MG-302 для protein\n'
        '        if role == "protein" and not is_cheat:',
        1,
    )

    # обернуть блок MG-502 (контроль масла): if is_cheat — пропускаем
    src = src.replace(
        "        # MG_502_503_V_generator: контроль масла (≤5 ч.л./день)\n        day_t = self.tracker.get_day(member_id, day_offset)\n        if float(day_t.get(\"oil_tsp\", 0.0)) > DAILY_OIL_TSP_LIMIT:",
        "        # MG_502_503_V_generator: контроль масла (≤5 ч.л./день)\n"
        "        # MG_505_V_pick_bypass: в cheat-meal не режем масляные\n"
        "        day_t = self.tracker.get_day(member_id, day_offset)\n"
        "        if not is_cheat and float(day_t.get(\"oil_tsp\", 0.0)) > DAILY_OIL_TSP_LIMIT:",
        1,
    )

    # обернуть MG-503 (исключение сахара)
    src = src.replace(
        "        # MG_502_503_V_generator: исключение сахара\n        # 1) основные приёмы: has_added_sugar=True вообще запрещено\n        if meal_type in MAIN_MEAL_TYPES:",
        "        # MG_502_503_V_generator: исключение сахара\n"
        "        # MG_505_V_pick_bypass: в cheat-meal сахар разрешён\n"
        "        # 1) основные приёмы: has_added_sugar=True вообще запрещено\n"
        "        if not is_cheat and meal_type in MAIN_MEAL_TYPES:",
        1,
    )
    # snack тоже надо отметить (на случай если в будущем cheat будет в snack)
    src = src.replace(
        "        elif meal_type == \"snack\":\n            if int(day_t.get(\"sweet_count\", 0)) >= SWEET_PER_DAY_LIMIT:",
        "        elif not is_cheat and meal_type == \"snack\":\n            if int(day_t.get(\"sweet_count\", 0)) >= SWEET_PER_DAY_LIMIT:",
        1,
    )

    # обернуть калорийный фильтр MG-303
    src = src.replace(
        "        # MG_303_V_generator: эскалирующий калорийный фильтр ±15% → ±30% → ±50%\n        if target_cal and target_cal > 0:",
        "        # MG_303_V_generator: эскалирующий калорийный фильтр ±15% → ±30% → ±50%\n"
        "        # MG_505_V_pick_bypass: в cheat-meal не фильтруем по калориям\n"
        "        if not is_cheat and target_cal and target_cal > 0:",
        1,
    )

    print("  pick_for_role bypass integrated")

# 5c) В основном цикле generate(): передаём is_cheat=True для protein-компонента cheat-приёма
if "MG_505_V_generate_loop" in src:
    print("  generate() loop already integrated, skip")
else:
    # Найти строку "for member in self.members:" и обернуть проверкой cheat-day
    # затем в "for role in roles:" добавить is_cheat для cheat-комбинации
    
    # Точечно: вставить cheat_slot вычисление сразу после "target_cal = self._get_calorie_target(member)"
    src = src.replace(
        "                target_cal = self._get_calorie_target(member)\n                hard_exclude = self._get_hard_exclude(member)\n",
        "                target_cal = self._get_calorie_target(member)\n"
        "                hard_exclude = self._get_hard_exclude(member)\n"
        "                # MG_505_V_generate_loop: cheat-day detection\n"
        "                _mg505_current_date = self.start_date + _mg505_timedelta(days=day)\n"
        "                _mg505_is_cheat = _mg505_is_cheat_day(member, _mg505_current_date)\n"
        "                _mg505_cheat_slot = _mg505_pick_cheat_slot(member.id, day) if _mg505_is_cheat else None\n",
        1,
    )

    # В вызов _pick_for_role передать is_cheat=...
    # Сейчас:
    #     recipe = self._pick_for_role(
    #         role=role,
    #         meal_type=db_meal_type,
    #         pools=pools,
    #         used=used_per_member[member.id],
    #         hard_exclude=hard_exclude,
    #         fridge_ids=fridge_ids,
    #         target_cal=per_role_cal,
    #         member_id=member.id,
    #         day_offset=day,
    #     )
    src = src.replace(
        "                            day_offset=day,\n                        )",
        "                            day_offset=day,\n"
        "                            is_cheat=(_mg505_is_cheat and meal_slot == _mg505_cheat_slot and role == \"protein\"),  # MG_505_V_generate_loop\n"
        "                        )",
        1,
    )

    # В items.append добавить is_cheat_meal
    src = src.replace(
        '                        items.append({\n'
        '                            "member":         member,\n'
        '                            "meal_type":      db_meal_type,\n'
        '                            "meal_slot":      meal_slot,\n'
        '                            "day_offset":     day,\n'
        '                            "recipe":         recipe,\n'
        '                            "component_role": role,\n'
        '                        })',
        '                        items.append({\n'
        '                            "member":         member,\n'
        '                            "meal_type":      db_meal_type,\n'
        '                            "meal_slot":      meal_slot,\n'
        '                            "day_offset":     day,\n'
        '                            "recipe":         recipe,\n'
        '                            "component_role": role,\n'
        '                            "is_cheat_meal":  bool(_mg505_is_cheat and meal_slot == _mg505_cheat_slot),  # MG_505_V_generate_loop\n'
        '                        })',
        1,
    )

    print("  generate() loop integrated")

p.write_text(src, encoding="utf-8")
PYEOF
echo

# ─── 6. views.py: bulk_create + last_cheat_meal_date update ───
echo "[6/8] patch apps/menu/views.py — bulk_create is_cheat_meal + update last_cheat_meal_date"
python3 <<'PYEOF'
from pathlib import Path
import re

p = Path("/opt/menugen/backend/apps/menu/views.py")
src = p.read_text(encoding="utf-8")

if "MG_505_V_views" in src:
    print("  already patched, skip")
else:
    # 1) В bulk_create MenuItem(...) добавить is_cheat_meal
    src = src.replace(
        '                    component_role=item.get("component_role", "other"),\n                )\n                for item in generated\n            ])',
        '                    component_role=item.get("component_role", "other"),\n'
        '                    is_cheat_meal=item.get("is_cheat_meal", False),  # MG_505_V_views\n'
        '                )\n'
        '                for item in generated\n'
        '            ])\n'
        '\n'
        '            # MG_505_V_views: обновить last_cheat_meal_date для членов, у которых в этом меню был cheat\n'
        '            from collections import defaultdict\n'
        '            from apps.menu.generator import _mg505_mark_cheat_meal_used\n'
        '            _mg505_seen = defaultdict(list)  # member_id -> list of (day_offset)\n'
        '            for it in generated:\n'
        '                if it.get("is_cheat_meal"):\n'
        '                    m = it.get("member")\n'
        '                    if m is not None:\n'
        '                        _mg505_seen[m.id].append(it.get("day_offset", 0))\n'
        '            for m in members:\n'
        '                if m.id in _mg505_seen:\n'
        '                    last_day = max(_mg505_seen[m.id])\n'
        '                    from datetime import timedelta as _mg505_td\n'
        '                    _mg505_mark_cheat_meal_used(m, start_date + _mg505_td(days=last_day))',
        1,
    )
    p.write_text(src, encoding="utf-8")
    print("  patched")
PYEOF
echo

# ─── 7. Migration ───
echo "[7/8] makemigrations + migrate"
$COMPOSE exec -T backend python manage.py makemigrations menu --name mg_505_menuitem_is_cheat_meal
$COMPOSE exec -T backend python manage.py migrate menu
echo

# ─── 8. Frontend types ───
echo "[8/8] patch web types/index.ts — MenuItem.is_cheat_meal"
python3 <<'PYEOF'
from pathlib import Path
import re

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

# ─── Sanity check syntax ───
echo "=== Python syntax check ==="
$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/models.py').read()); print('  models OK')"
$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/serializers.py').read()); print('  serializers OK')"
$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/generator.py').read()); print('  generator OK')"
$COMPOSE exec -T backend python -c "import ast; ast.parse(open('apps/menu/views.py').read()); print('  views OK')"
echo

echo "=== Django check ==="
$COMPOSE exec -T backend python manage.py check
echo

echo "=== MG-505 APPLY DONE ==="
echo "Дальше: создать тесты + регрессия"
