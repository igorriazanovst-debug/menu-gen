#!/usr/bin/env bash
# MG-605.A: мульти-член mode (per_member / family) в генераторе меню.
#
# Что делает:
# - apps/menu/serializers.py: добавляет mode (per_member | family, default=family)
# - apps/menu/generator.py: новый метод _generate_family() — единый прогон,
#   потом дублирование под каждого с индивидуальной quantity.
#   Существующий generate() работает в режиме per_member (как было).
# - apps/menu/views.py: пробрасывает mode в генератор и в Menu.filters_used.
# - apps/menu/portions.py: расширяется функцией member_quantity_for_recipe().
#
# Backup в /tmp/mg_605a_backup_<TS>/
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
MENU="$BACKEND/apps/menu"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_605a_backup_${TS}"

mkdir -p "$BAK"
echo "[1/6] Backup → $BAK"
for f in serializers.py generator.py views.py portions.py; do
  cp -v "$MENU/$f" "$BAK/$f"
done

# ─────────────────────────────────────────────────────────────────────────────
# [2/6] portions.py — добавить member_quantity_for_recipe()
# ─────────────────────────────────────────────────────────────────────────────
echo "[2/6] portions.py — добавляем member_quantity_for_recipe()"

if ! grep -q "def member_quantity_for_recipe" "$MENU/portions.py"; then
cat >> "$MENU/portions.py" <<'PYEOF'


# MG_605A_V_portions
def member_quantity_for_recipe(member, recipe, ref_date=None) -> float:
    """
    605.A: вес порции одного члена семьи в рецепте, нормированный к взрослой норме.

    Возвращает коэффициент quantity для MenuItem.quantity в режиме mode=family
    (когда все члены едят одни и те же рецепты, но порции разные).

    Базовая логика: quantity = age_multiplier(member) — то есть взрослый = 1.0,
    подросток 11-13 = 0.85, ребёнок 7-10 = 0.70 и т.д.
    Это согласуется с возрастной кривой daily_target_grams.
    """
    age = _member_age(member, ref_date)
    return _age_multiplier(age)
PYEOF
  echo "  portions.py: добавлено"
else
  echo "  portions.py: member_quantity_for_recipe уже есть, пропуск"
fi

# ─────────────────────────────────────────────────────────────────────────────
# [3/6] serializers.py — добавить поле mode
# ─────────────────────────────────────────────────────────────────────────────
echo "[3/6] serializers.py — добавляем поле mode в GenerateMenuSerializer"

python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/serializers.py")
src = p.read_text(encoding="utf-8")

if "MG_605A_V_serializers" in src:
    print("  serializers.py: уже пропатчен")
else:
    new_field = (
        "    # MG_605A_V_serializers: mode мульти-член (per_member | family)\n"
        "    mode = serializers.ChoiceField(\n"
        "        choices=['per_member', 'family'], default='family', required=False\n"
        "    )\n"
    )
    # Вставляем после meal_plan_type внутри GenerateMenuSerializer
    pattern = r"(meal_plan_type = serializers\.ChoiceField\([^)]*\)\n)"
    if re.search(pattern, src):
        src = re.sub(pattern, r"\1" + new_field, src, count=1)
        p.write_text(src, encoding="utf-8")
        print("  serializers.py: поле mode добавлено")
    else:
        raise SystemExit("ОШИБКА: не найден meal_plan_type в GenerateMenuSerializer")
PYEOF

# ─────────────────────────────────────────────────────────────────────────────
# [4/6] generator.py — добавить mode + _generate_family()
# ─────────────────────────────────────────────────────────────────────────────
echo "[4/6] generator.py — добавляем mode + _generate_family()"

python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

if "MG_605A_V_generator" in src:
    print("  generator.py: уже пропатчен")
    raise SystemExit(0)

# 1) Читаем mode из filters в __init__
old_init_tail = (
    '        meal_count = self.filters.get("meal_plan_type", "3")\n'
    '        self.meal_types = MEAL_PLAN_5 if str(meal_count) == "5" else MEAL_PLAN_3\n'
)
new_init_tail = (
    '        meal_count = self.filters.get("meal_plan_type", "3")\n'
    '        self.meal_types = MEAL_PLAN_5 if str(meal_count) == "5" else MEAL_PLAN_3\n'
    '        # MG_605A_V_generator: режим мульти-член\n'
    '        self.mode = str(self.filters.get("mode", "family"))\n'
    '        if self.mode not in ("per_member", "family"):\n'
    '            self.mode = "family"\n'
)
if old_init_tail not in src:
    raise SystemExit("ОШИБКА: не нашёл точку вставки mode в __init__")
src = src.replace(old_init_tail, new_init_tail, 1)

# 2) Развилка в generate(): если mode=family и членов >1 → _generate_family()
old_generate_head = (
    '    def generate(self) -> List[dict]:\n'
    '        all_recipes = self._build_recipe_pool()\n'
)
new_generate_head = (
    '    def generate(self) -> List[dict]:\n'
    '        # MG_605A_V_generator: режим family — один прогон, дублирование под членов\n'
    '        if self.mode == "family" and len(self.members) > 1:\n'
    '            return self._generate_family()\n'
    '        all_recipes = self._build_recipe_pool()\n'
)
if old_generate_head not in src:
    raise SystemExit("ОШИБКА: не нашёл начало generate()")
src = src.replace(old_generate_head, new_generate_head, 1)

# 3) Добавляем метод _generate_family() и _family_virtual_member() в конец класса
# Найдём последний метод класса MenuGenerator перед концом файла
family_method = '''
    # MG_605A_V_generator: family-режим — один прогон на «виртуального главу»,
    # потом дублирование MenuItem для каждого члена с индивидуальной quantity.
    def _generate_family(self) -> List[dict]:
        from .portions import member_quantity_for_recipe

        all_recipes = self._build_recipe_pool()
        pools = self._build_pools_by_role(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items: List[dict] = []

        # Виртуальный «представитель семьи»: union allergies/disliked, средний calorie_target
        virt = self._family_virtual_member()

        # used общий для всей семьи — не повторяем рецепты в течение недели
        used: set = set()

        for day in range(self.period_days):
            target_cal = virt["calorie_target"]
            hard_exclude = virt["hard_exclude"]
            # MG_505: cheat-day для family-режима пропускаем (он per-member)
            for meal_slot in self.meal_types:
                db_meal_type = MEAL_TYPE_DB[meal_slot]
                roles = MEAL_COMPONENTS.get(meal_slot, ("other",))
                per_meal_cal = self._meal_target_cal(target_cal, meal_slot)
                per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

                # Для warnings _meal_cal_target пишем под каждого члена
                for m in self.members:
                    self._meal_cal_target[(m.id, day, meal_slot)] = per_meal_cal

                for role in roles:
                    recipe = self._pick_for_role(
                        role=role,
                        meal_type=db_meal_type,
                        pools=pools,
                        used=used,
                        hard_exclude=hard_exclude,
                        fridge_ids=fridge_ids,
                        target_cal=per_role_cal,
                        member_id=0,  # обобщённый
                        day_offset=day,
                        is_cheat=False,
                    )
                    if recipe is None:
                        err = EmptyRolePoolError(
                            role=role,
                            meal_slot=meal_slot,
                            day_offset=day,
                            member_name="семья",
                        )
                        logger.warning(
                            "MG-605A family empty role pool: role=%s slot=%s day=%s",
                            role, meal_slot, day,
                        )
                        raise err

                    used.add(recipe.id)
                    rcal = self._recipe_cal(recipe)

                    # Дублируем item для каждого члена с индивидуальной quantity
                    for member in self.members:
                        self.tracker.add(member.id, day, recipe)
                        if rcal is not None:
                            self._meal_cal_actual[(member.id, day, meal_slot)] += float(rcal)
                        items.append({
                            "member":         member,
                            "meal_type":      db_meal_type,
                            "meal_slot":      meal_slot,
                            "day_offset":     day,
                            "recipe":         recipe,
                            "component_role": role,
                            "is_cheat_meal":  False,
                            "quantity":       round(member_quantity_for_recipe(
                                                  member, recipe, ref_date=self.start_date
                                              ), 2),
                        })

        # Догон овощей/фруктов — используем существующий метод per-member
        used_per_member = {m.id: set(used) for m in self.members}
        warnings: list = []
        warnings.extend(self._ensure_veg_fruit_servings(
            items=items, pools=pools,
            used_per_member=used_per_member, fridge_ids=fridge_ids,
        ))
        warnings.extend(self._collect_weekly_warnings())
        warnings.extend(self._collect_daily_plant_warnings())
        warnings.extend(self._collect_meal_calorie_warnings())
        self.last_warnings = warnings
        return items

    def _family_virtual_member(self) -> dict:
        """605.A: union allergies/disliked, средний calorie_target по семье."""
        exclude = set()
        cals = []
        for m in self.members:
            user = m.user
            if isinstance(user.allergies, list):
                exclude.update(a.lower() for a in user.allergies)
            if self.features.get("disliked") and isinstance(user.disliked_products, list):
                exclude.update(d.lower() for d in user.disliked_products)
            if self.features.get("calories"):
                try:
                    c = user.profile.calorie_target
                    if c:
                        cals.append(int(c))
                except Exception:
                    pass
        avg_cal = int(sum(cals) / len(cals)) if cals else None
        return {"hard_exclude": exclude, "calorie_target": avg_cal}
'''

# Вставляем перед классом _WeeklyTracker или в конец файла
# Найдём конец класса MenuGenerator (последний метод _recipe_passes_hard / _recipe_cal)
# Простой способ: вставка перед строкой с шапкой следующего класса/функции на верхнем уровне.
# Если такого нет — в конец файла.

# Найдём ПОСЛЕДНИЙ метод класса MenuGenerator. Лучше всего — добавить перед последней
# строкой, относящейся к классу. Простейшее: добавить в конец файла, т.к. в этом
# модуле других классов после MenuGenerator нет (по диагностике).

# Проверка: после `class MenuGenerator` нет других определений верхнего уровня
m = re.search(r"^class MenuGenerator", src, flags=re.MULTILINE)
if not m:
    raise SystemExit("ОШИБКА: не нашёл class MenuGenerator")
# Найдём всё после class MenuGenerator и убедимся что после него нет других классов
tail = src[m.end():]
other = re.search(r"^(class |def )", tail, flags=re.MULTILINE)
if other:
    # есть что-то ниже — вставим перед ним
    insert_pos = m.end() + other.start()
    src = src[:insert_pos] + family_method + "\n\n" + src[insert_pos:]
else:
    # просто в конец файла
    if not src.endswith("\n"):
        src += "\n"
    src += family_method + "\n"

p.write_text(src, encoding="utf-8")
print("  generator.py: добавлены mode + _generate_family() + _family_virtual_member()")
PYEOF

# ─────────────────────────────────────────────────────────────────────────────
# [5/6] views.py — пробросить mode в filters
# ─────────────────────────────────────────────────────────────────────────────
echo "[5/6] views.py — пробрасываем mode"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/menu/views.py")
src = p.read_text(encoding="utf-8")

if "MG_605A_V_views" in src:
    print("  views.py: уже пропатчен")
    raise SystemExit(0)

# После блока if data.get("meal_plan_type"): добавляем mode
old = (
    '        if data.get("meal_plan_type"):\n'
    '            filters["meal_plan_type"] = data["meal_plan_type"]\n'
)
new = (
    '        if data.get("meal_plan_type"):\n'
    '            filters["meal_plan_type"] = data["meal_plan_type"]\n'
    '        # MG_605A_V_views: проброс mode (per_member | family)\n'
    '        filters["mode"] = data.get("mode", "family")\n'
)
if old not in src:
    raise SystemExit("ОШИБКА: не нашёл блок meal_plan_type в views.py")
src = src.replace(old, new, 1)

# В MenuItem.bulk_create — пробрасываем quantity из items (для family режима)
# Сейчас: quantity не передаётся → default=1. Нужно: item.get("quantity", 1)
old_bulk = (
    '                MenuItem(\n'
    '                    menu=menu,\n'
    '                    recipe=item["recipe"],\n'
    '                    member=item["member"],\n'
    '                    meal_type=item["meal_type"],\n'
    '                    meal_slot=item.get("meal_slot", item["meal_type"]),\n'
    '                    day_offset=item["day_offset"],\n'
    '                    component_role=item.get("component_role", "other"),\n'
    '                    is_cheat_meal=item.get("is_cheat_meal", False),  # MG_505_V_views\n'
    '                )\n'
)
new_bulk = (
    '                MenuItem(\n'
    '                    menu=menu,\n'
    '                    recipe=item["recipe"],\n'
    '                    member=item["member"],\n'
    '                    meal_type=item["meal_type"],\n'
    '                    meal_slot=item.get("meal_slot", item["meal_type"]),\n'
    '                    day_offset=item["day_offset"],\n'
    '                    component_role=item.get("component_role", "other"),\n'
    '                    is_cheat_meal=item.get("is_cheat_meal", False),  # MG_505_V_views\n'
    '                    quantity=item.get("quantity", 1),  # MG_605A_V_views\n'
    '                )\n'
)
if old_bulk in src:
    src = src.replace(old_bulk, new_bulk, 1)
    print("  views.py: bulk_create patched (quantity)")
else:
    print("  views.py: bulk_create без quantity — пропуск (возможно уже патчили)")

p.write_text(src, encoding="utf-8")
print("  views.py: mode проброшен")
PYEOF

# ─────────────────────────────────────────────────────────────────────────────
# [6/6] Проверка syntax + smoke pytest
# ─────────────────────────────────────────────────────────────────────────────
echo "[6/6] syntax check + регрессионные тесты"
$COMPOSE exec -T backend python -c "
import importlib
for mod in ('apps.menu.portions', 'apps.menu.serializers', 'apps.menu.generator', 'apps.menu.views'):
    importlib.import_module(mod)
    print(f'  OK: {mod}')
"
echo
echo "[regression] pytest apps/menu (быстрый прогон без новых тестов)"
$COMPOSE exec -T backend pytest apps/menu/ -q --tb=short 2>&1 | tail -20
echo
echo "=== 605.A apply done. Backup: $BAK ==="
