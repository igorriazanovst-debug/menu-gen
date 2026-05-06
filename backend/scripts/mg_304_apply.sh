#!/bin/bash
# MG-304 apply: 5 порций овощей/фруктов в день (per member, по граммам с учётом возраста).
#   - Menu.warnings JSONField (миграция 0007)
#   - portions.py: целевая граммовка/день и вес порции рецепта
#   - generator.py: добивание snack-слотами + warnings
#   - views.py: сохранение warnings
#   - serializers.py: отдача warnings в API
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="$ROOT/docker-compose.yml"
MENU="$BACKEND/apps/menu"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_304_backup_${TS}"

mkdir -p "$BAK"
echo "[1/8] Backup -> $BAK"
for f in models.py generator.py views.py serializers.py exceptions.py; do
  cp -v "$MENU/$f" "$BAK/$f"
done
cp -rv "$MENU/migrations" "$BAK/migrations"

echo
echo "[2/8] Создаю apps/menu/portions.py (MG-304)"
cat > "$MENU/portions.py" <<'PYEOF'
"""
MG-304: расчёт суточной нормы овощей+фруктов в граммах per member и веса
порции конкретного рецепта.

Цель — гарантировать, что в дневном меню каждого члена семьи присутствует
эквивалент 5 порций овощей/фруктов (для взрослого 1 порция ≈ 150 г → 750 г/сутки),
скорректированный по возрасту плавной формулой.

Источник веса порции рецепта (приоритеты, fallback вниз):
  1) Recipe.nutrition.weight.value  (граммы на 1 порцию)
  2) Recipe.povar_raw.dish_weight_g_calc / servings_normalized (или servings)
  3) DEFAULT_PORTION_G_FALLBACK = 200 г (страховка для редких пустых)
"""
# MG_304_V_portions
from __future__ import annotations
from datetime import date
from typing import Optional

ADULT_PORTION_G       = 150.0
PORTIONS_PER_DAY      = 5
DEFAULT_PORTION_G_FALLBACK = 200.0

# плавная коррекция нормы по возрасту (множитель к ADULT_PORTION_G * 5)
# < 4 года   → 0.40
# 4..6       → 0.55
# 7..10      → 0.70
# 11..13     → 0.85
# >=14       → 1.00 (взрослая норма)
def _age_multiplier(age: Optional[int]) -> float:
    if age is None:
        return 1.0
    if age < 0:
        return 1.0
    if age < 4:
        return 0.40
    if age < 7:
        return 0.55
    if age < 11:
        return 0.70
    if age < 14:
        return 0.85
    return 1.00


def _member_age(member, ref_date: Optional[date] = None) -> Optional[int]:
    """Возраст члена семьи на ref_date по profile.birth_year. None если нет данных."""
    try:
        profile = getattr(member.user, "profile", None)
        by = getattr(profile, "birth_year", None)
        if not by:
            return None
        ref = ref_date or date.today()
        return max(0, ref.year - int(by))
    except Exception:
        return None


def daily_target_grams(member, ref_date: Optional[date] = None) -> float:
    """Целевая суточная граммовка овощей+фруктов для члена семьи (гр)."""
    age = _member_age(member, ref_date)
    return ADULT_PORTION_G * PORTIONS_PER_DAY * _age_multiplier(age)


def recipe_portion_grams(recipe) -> float:
    """
    Вес 1 порции рецепта в граммах.
    Приоритеты: nutrition.weight.value → povar_raw.dish_weight_g_calc / servings → fallback.
    """
    # 1) nutrition.weight.value
    try:
        nut = recipe.nutrition or {}
        w = nut.get("weight") if isinstance(nut, dict) else None
        if isinstance(w, dict):
            v = w.get("value")
        else:
            v = w
        if v not in (None, "", 0, "0"):
            g = float(str(v).replace(",", "."))
            if g > 0:
                return g
    except Exception:
        pass

    # 2) povar_raw.dish_weight_g_calc / servings_normalized (или servings)
    try:
        pr = getattr(recipe, "povar_raw", None) or {}
        dw = pr.get("dish_weight_g_calc")
        sn = getattr(recipe, "servings_normalized", None) or getattr(recipe, "servings", None) or 1
        if dw and sn:
            g = float(dw) / float(sn)
            if g > 0:
                return g
    except Exception:
        pass

    return DEFAULT_PORTION_G_FALLBACK
PYEOF
echo "  OK -> $MENU/portions.py"

echo
echo "[3/8] Миграция 0007_menu_warnings"
cat > "$MENU/migrations/0007_menu_warnings.py" <<'PYEOF'
# MG_304_V_migration
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0006_component_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="menu",
            name="warnings",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
PYEOF
echo "  OK -> 0007_menu_warnings.py"

echo
echo "[4/8] models.py: добавляем Menu.warnings"
python3 - "$MENU/models.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

if "MG_304_V_models" in src:
    print("  models.py уже содержит маркер MG_304_V_models — пропуск"); sys.exit(0)

# Ищем класс Menu и поле filters_used — вставим warnings рядом.
pat = r"(filters_used\s*=\s*models\.JSONField\([^)]*\))"
m = re.search(pat, src)
if not m:
    print("ERROR: не найден filters_used в models.py", file=sys.stderr); sys.exit(1)

inject = m.group(1) + "\n    warnings = models.JSONField(blank=True, default=list)  # MG_304_V_models"
new = src[:m.start()] + inject + src[m.end():]
p.write_text(new, encoding="utf-8")
print("  models.py: warnings добавлен")
PYEOF

echo
echo "[5/8] generator.py: добивание snack-порциями + сбор warnings"
python3 - "$MENU/generator.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

if "MG_304_V_generator" in src:
    print("  generator.py уже содержит маркер MG_304_V_generator — пропуск"); sys.exit(0)

# 5.1 — импорт portions
src = src.replace(
    "from .exceptions import EmptyRolePoolError",
    "from .exceptions import EmptyRolePoolError\n"
    "from .portions import daily_target_grams, recipe_portion_grams  # MG_304_V_generator",
    1,
)

# 5.2 — заменить хвост generate() (return items) на сбор недобора + warnings
old_tail = "                        items.append({\n" \
           "                            \"member\":         member,\n" \
           "                            \"meal_type\":      db_meal_type,\n" \
           "                            \"meal_slot\":      meal_slot,\n" \
           "                            \"day_offset\":     day,\n" \
           "                            \"recipe\":         recipe,\n" \
           "                            \"component_role\": role,\n" \
           "                        })\n" \
           "        return items\n"

new_tail = "                        items.append({\n" \
           "                            \"member\":         member,\n" \
           "                            \"meal_type\":      db_meal_type,\n" \
           "                            \"meal_slot\":      meal_slot,\n" \
           "                            \"day_offset\":     day,\n" \
           "                            \"recipe\":         recipe,\n" \
           "                            \"component_role\": role,\n" \
           "                        })\n" \
           "\n" \
           "        # MG_304_V_generator: 5 порций овощей/фруктов в день (per member)\n" \
           "        warnings = self._ensure_veg_fruit_servings(\n" \
           "            items=items,\n" \
           "            pools=pools,\n" \
           "            used_per_member=used_per_member,\n" \
           "            fridge_ids=fridge_ids,\n" \
           "        )\n" \
           "        self.last_warnings = warnings\n" \
           "        return items\n"

if old_tail not in src:
    print("ERROR: не нашёл ожидаемый хвост generate()", file=sys.stderr); sys.exit(1)
src = src.replace(old_tail, new_tail, 1)

# 5.3 — добавить метод _ensure_veg_fruit_servings перед "# ── pools"
helper = """
    # ── MG-304: добор порций овощей/фруктов ──────────────────────────────────
    def _ensure_veg_fruit_servings(self, items, pools, used_per_member, fridge_ids):
        \"\"\"
        Гарантирует целевой суточный объём овощей+фруктов per member (в граммах).
        Если до целевого граммажа не хватает — добавляет виртуальные snack-слоты
        с рецептами из пулов vegetable/fruit (без увеличения уже сгенерированных
        приёмов). Возвращает список warnings: список объектов с member/day/...
        \"\"\"
        from .portions import daily_target_grams, recipe_portion_grams

        warnings: list = []
        # Накопленные граммы veg+fruit по (member_id, day)
        grams: dict = {}
        for it in items:
            if it.get("component_role") in ("vegetable", "fruit"):
                key = (it["member"].id, it["day_offset"])
                grams[key] = grams.get(key, 0.0) + recipe_portion_grams(it["recipe"])

        # Объединённый пул veg+fruit (по food_group)
        veg_fruit_pool = list(pools.get("vegetable", [])) + list(pools.get("fruit", []))

        # Сколько уже виртуальных snack-слотов добавлено per (member, day),
        # чтобы их meal_slot был уникален (snack3, snack4, snack5, ...).
        existing_snack_slots = {}
        for it in items:
            if it.get("meal_slot", "").startswith("snack"):
                key = (it["member"].id, it["day_offset"])
                existing_snack_slots[key] = existing_snack_slots.get(key, 0) + 1

        for member in self.members:
            target = daily_target_grams(member, ref_date=self.start_date)
            for day in range(self.period_days):
                key = (member.id, day)
                have = grams.get(key, 0.0)
                if have >= target:
                    continue

                # Жёсткий фильтр (аллергии/нелюбимое) для этого члена
                hard_exclude = self._get_hard_exclude(member)

                # Перебираем кандидатов до закрытия дефицита (или пока есть)
                added = 0
                MAX_ADD = 5  # safety
                while have < target and added < MAX_ADD:
                    candidate = None
                    for r in veg_fruit_pool:
                        if r.id in used_per_member[member.id]:
                            continue
                        if not self._allowed_for_member(r, hard_exclude):
                            continue
                        candidate = r
                        break

                    if candidate is None:
                        break

                    used_per_member[member.id].add(candidate.id)
                    base_idx = existing_snack_slots.get(key, 0)
                    slot_n = base_idx + added + 1
                    items.append({
                        "member":         member,
                        "meal_type":      "snack",
                        "meal_slot":      f"snack{slot_n}",
                        "day_offset":     day,
                        "recipe":         candidate,
                        "component_role": candidate.food_group if candidate.food_group in ("vegetable", "fruit") else "vegetable",
                        "is_virtual":     True,  # MG_304_V_generator
                    })
                    have += recipe_portion_grams(candidate)
                    added += 1

                if have < target:
                    warnings.append({
                        "code":           "veg_fruit_shortfall",
                        "member_id":      member.id,
                        "member_name":    self._member_display_name(member),
                        "day_offset":     day,
                        "target_grams":   round(target, 1),
                        "actual_grams":   round(have, 1),
                        "missing_grams":  round(target - have, 1),
                    })
        return warnings
"""

src = src.replace(
    "    # ── pools ────────────────────────────────────────────────────────────────",
    helper + "    # ── pools ────────────────────────────────────────────────────────────────",
    1,
)

p.write_text(src, encoding="utf-8")
print("  generator.py: добавлен _ensure_veg_fruit_servings + сбор warnings")
PYEOF

echo
echo "[6/8] views.py: сохраняем Menu.warnings + bulk_create без is_virtual"
python3 - "$MENU/views.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

if "MG_304_V_views" in src:
    print("  views.py уже содержит маркер MG_304_V_views — пропуск"); sys.exit(0)

# 6.1 — после generated = generator.generate() читаем generator.last_warnings
src = src.replace(
    "            generated = generator.generate()",
    "            generated = generator.generate()\n"
    "            warnings_list = list(getattr(generator, \"last_warnings\", []) or [])  # MG_304_V_views",
    1,
)

# 6.2 — Menu.objects.create(...filters_used=filters,) → +warnings=warnings_list
src = src.replace(
    "                filters_used=filters,\n            )",
    "                filters_used=filters,\n"
    "                warnings=warnings_list,  # MG_304_V_views\n"
    "            )",
    1,
)

p.write_text(src, encoding="utf-8")
print("  views.py: подключены warnings")
PYEOF

echo
echo "[7/8] serializers.py: warnings в MenuDetailSerializer"
python3 - "$MENU/serializers.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")
if "MG_304_V_serializers" in src:
    print("  serializers.py уже содержит маркер MG_304_V_serializers — пропуск"); sys.exit(0)

# Печатаем текущий файл — чтобы понять, какие классы есть
print("  serializers.py len:", len(src), "строк:", src.count("\n"))
print(src)
PYEOF

# Найдём имя класса детального сериализатора и добавим warnings
python3 - "$MENU/serializers.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path("/opt/menugen/backend/apps/menu/serializers.py")
src = p.read_text(encoding="utf-8")
if "MG_304_V_serializers" in src:
    sys.exit(0)

# Ищем class MenuDetailSerializer и его Meta.fields
m = re.search(r"class\s+MenuDetailSerializer\b[^:]*:\s*(.+?)(?=^class\s|\Z)", src, re.DOTALL | re.MULTILINE)
if not m:
    print("WARN: MenuDetailSerializer не найден — пропуск", file=sys.stderr); sys.exit(0)

cls_block = m.group(0)
# Добавляем "warnings" в Meta.fields, если его нет
fm = re.search(r"fields\s*=\s*([\[(])([^\])]*)([\])])", cls_block)
if not fm:
    print("WARN: Meta.fields в MenuDetailSerializer не найден — пропуск", file=sys.stderr); sys.exit(0)

if "warnings" in fm.group(2):
    print("  warnings уже в fields"); sys.exit(0)

new_fields = fm.group(1) + fm.group(2).rstrip().rstrip(",") + ', "warnings"' + fm.group(3) + "  # MG_304_V_serializers"
new_cls = cls_block.replace(fm.group(0), new_fields)
src = src.replace(cls_block, new_cls)
p.write_text(src, encoding="utf-8")
print("  serializers.py: warnings добавлен в MenuDetailSerializer.Meta.fields")
PYEOF

echo
echo "[8/8] migrate + collect imports check"
docker compose -f "$COMPOSE" exec -T backend python manage.py migrate menu
echo
echo "import smoke (внутри Django shell):"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell <<'PYEOF'
from apps.menu.generator import MenuGenerator, MEAL_PLAN_3, MEAL_PLAN_5
from apps.menu.portions import daily_target_grams, recipe_portion_grams, ADULT_PORTION_G, PORTIONS_PER_DAY
from apps.menu.models import Menu
print("Menu.warnings field:", "warnings" in {f.name for f in Menu._meta.get_fields()})
print("ADULT_PORTION_G * PORTIONS_PER_DAY =", ADULT_PORTION_G * PORTIONS_PER_DAY)
PYEOF

echo
echo "=========================================="
echo "  MG-304 APPLY: DONE   (backup: $BAK)"
echo "=========================================="
