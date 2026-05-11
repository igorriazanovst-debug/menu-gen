#!/usr/bin/env bash
# MG-605.A fix: переписать только generator.py (откат + правильная вставка)
set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
GEN="$ROOT/backend/apps/menu/generator.py"

# Найти последний бэкап
BAK_DIR=$(ls -td /tmp/mg_605a_backup_* 2>/dev/null | head -1)
if [ -z "$BAK_DIR" ]; then
  echo "ОШИБКА: бэкап /tmp/mg_605a_backup_* не найден"
  exit 1
fi
echo "[1] Восстанавливаю generator.py из бэкапа $BAK_DIR"
cp -v "$BAK_DIR/generator.py" "$GEN"

echo
echo "[2] Применяю правильный патч в generator.py"

python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

# ── 1) __init__: добавить self.mode ────────────────────────────────────────
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
assert old_init_tail in src, "не нашёл точку __init__"
src = src.replace(old_init_tail, new_init_tail, 1)
print("  __init__: self.mode добавлен")

# ── 2) generate(): развилка ─────────────────────────────────────────────────
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
assert old_generate_head in src, "не нашёл generate()"
src = src.replace(old_generate_head, new_generate_head, 1)
print("  generate(): развилка добавлена")

# ── 3) Вставка _generate_family() и _family_virtual_member() ────────────────
# Вставляем перед методом _get_hard_exclude (он есть, на 652 строке диагностики)

family_methods = '''    # MG_605A_V_generator: family-режим — один прогон, дублирование под членов
    def _generate_family(self) -> List[dict]:
        from .portions import member_quantity_for_recipe

        all_recipes = self._build_recipe_pool()
        pools = self._build_pools_by_role(all_recipes)
        fridge_ids = self._get_fridge_ingredient_names()
        items: List[dict] = []

        virt = self._family_virtual_member()
        used: set = set()

        for day in range(self.period_days):
            target_cal = virt["calorie_target"]
            hard_exclude = virt["hard_exclude"]
            for meal_slot in self.meal_types:
                db_meal_type = MEAL_TYPE_DB[meal_slot]
                roles = MEAL_COMPONENTS.get(meal_slot, ("other",))
                per_meal_cal = self._meal_target_cal(target_cal, meal_slot)
                per_role_cal = (per_meal_cal / len(roles)) if per_meal_cal else None

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
                        member_id=0,
                        day_offset=day,
                        is_cheat=False,
                    )
                    if recipe is None:
                        err = EmptyRolePoolError(
                            role=role,
                            meal_slot=meal_slot,
                            day_offset=day,
                            member_name="family",
                        )
                        logger.warning(
                            "MG-605A family empty role pool: role=%s slot=%s day=%s",
                            role, meal_slot, day,
                        )
                        raise err

                    used.add(recipe.id)
                    rcal = self._recipe_cal(recipe)

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

    # MG_605A_V_generator: «виртуальный представитель семьи»
    def _family_virtual_member(self) -> dict:
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

# Вставка перед существующим методом _get_hard_exclude
anchor = '    def _get_hard_exclude(self, member) -> set:\n'
assert anchor in src, "не нашёл _get_hard_exclude как точку вставки"
src = src.replace(anchor, family_methods + anchor, 1)
print("  _generate_family + _family_virtual_member: вставлены перед _get_hard_exclude")

p.write_text(src, encoding="utf-8")
print("\nDONE")
PYEOF

echo
echo "[3] Проверка отступов: первые 5 строк _generate_family"
grep -n "def _generate_family\|def _family_virtual_member\|def _get_hard_exclude" "$GEN"
echo

echo "[4] py_compile generator.py"
$COMPOSE exec -T backend python -m py_compile apps/menu/generator.py && echo "  OK"
echo

echo "[5] Django check"
$COMPOSE exec -T backend python manage.py check 2>&1 | tail -5
echo

echo "[6] Регресс apps/menu (быстрый)"
$COMPOSE exec -T backend pytest apps/menu/ -q --tb=short 2>&1 | tail -20
echo

echo "[7] Регресс apps/recipes (быстрый)"
$COMPOSE exec -T backend pytest apps/recipes/ -q --tb=short 2>&1 | tail -8
echo

echo "=== 605.A fix done ==="
