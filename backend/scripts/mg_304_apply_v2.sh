#!/bin/bash
# MG-304 apply v2 — патчим generator.py детерминированно (regex по reg-сигнатурам).
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="$ROOT/docker-compose.yml"
MENU="$BACKEND/apps/menu"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_304_v2_backup_${TS}"

mkdir -p "$BAK"
cp -v "$MENU/generator.py" "$BAK/generator.py"
echo "Backup -> $BAK"

python3 - "$MENU/generator.py" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

# 0) Импорт portions (если ещё нет)
if "from .portions import daily_target_grams, recipe_portion_grams" not in src:
    src = src.replace(
        "from .exceptions import EmptyRolePoolError",
        "from .exceptions import EmptyRolePoolError\n"
        "from .portions import daily_target_grams, recipe_portion_grams  # MG_304_V_generator",
        1,
    )

# 1) Найти def generate(self) -> List[dict]: ... до следующего def на том же отступе
m = re.search(r"\n(    )def generate\(self\) -> List\[dict\]:\n", src)
if not m:
    print("FATAL: не нашёл def generate", file=sys.stderr); sys.exit(1)
start = m.end()
m2 = re.search(r"\n    def [A-Za-z_]+\(", src[start:])
if not m2:
    print("FATAL: не нашёл следующий метод после generate", file=sys.stderr); sys.exit(1)
end = start + m2.start()
body = src[start:end]

# 2) Заменить последний "        return items\n" внутри тела generate
ret_re = re.compile(r"\n([ \t]+)return items\n", re.MULTILINE)
matches = list(ret_re.finditer(body))
if not matches:
    print("FATAL: 'return items' не найден в generate()", file=sys.stderr); sys.exit(1)
last = matches[-1]
indent = last.group(1)
inject = (
    f"\n{indent}# MG_304_V_generator: 5 порций овощей/фруктов в день (per member)\n"
    f"{indent}warnings = self._ensure_veg_fruit_servings(\n"
    f"{indent}    items=items,\n"
    f"{indent}    pools=pools,\n"
    f"{indent}    used_per_member=used_per_member,\n"
    f"{indent}    fridge_ids=fridge_ids,\n"
    f"{indent})\n"
    f"{indent}self.last_warnings = warnings\n"
    f"{indent}return items\n"
)

# Если уже стоит маркер — пропуск
if "MG_304_V_generator: 5 порций" not in body:
    new_body = body[:last.start()] + inject + body[last.end():]
    src = src[:start] + new_body + src[end:]
    print("OK: generate() пропатчен, indent =", repr(indent))
else:
    print("SKIP: generate() уже содержит маркер")

# 3) Добавить _ensure_veg_fruit_servings перед "# ── pools" (если ещё нет)
if "_ensure_veg_fruit_servings" not in src:
    helper = '''
    # ── MG-304: добор порций овощей/фруктов ──────────────────────────────────
    def _ensure_veg_fruit_servings(self, items, pools, used_per_member, fridge_ids):
        """
        Гарантирует целевой суточный объём овощей+фруктов per member (в граммах).
        При недоборе добавляет виртуальные snack-слоты с рецептами из пулов
        vegetable/fruit. Возвращает список warnings (объекты при остаточном недоборе).
        """
        warnings: list = []
        grams: dict = {}
        for it in items:
            if it.get("component_role") in ("vegetable", "fruit"):
                key = (it["member"].id, it["day_offset"])
                grams[key] = grams.get(key, 0.0) + recipe_portion_grams(it["recipe"])

        veg_fruit_pool = list(pools.get("vegetable", [])) + list(pools.get("fruit", []))

        existing_snack_slots = {}
        for it in items:
            slot = it.get("meal_slot", "") or ""
            if slot.startswith("snack"):
                key = (it["member"].id, it["day_offset"])
                existing_snack_slots[key] = existing_snack_slots.get(key, 0) + 1

        for member in self.members:
            target = daily_target_grams(member, ref_date=self.start_date)
            for day in range(self.period_days):
                key = (member.id, day)
                have = grams.get(key, 0.0)
                if have >= target:
                    continue

                hard_exclude = self._get_hard_exclude(member)
                added = 0
                MAX_ADD = 5
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
                    role = candidate.food_group if candidate.food_group in ("vegetable", "fruit") else "vegetable"
                    items.append({
                        "member":         member,
                        "meal_type":      "snack",
                        "meal_slot":      f"snack{slot_n}",
                        "day_offset":     day,
                        "recipe":         candidate,
                        "component_role": role,
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

'''
    pools_marker = "    # ── pools"
    if pools_marker in src:
        src = src.replace(pools_marker, helper + pools_marker, 1)
        print("OK: _ensure_veg_fruit_servings добавлен перед '# ── pools'")
    else:
        print("FATAL: не найден маркер '# ── pools' для вставки helper'а", file=sys.stderr); sys.exit(1)
else:
    print("SKIP: _ensure_veg_fruit_servings уже есть")

p.write_text(src, encoding="utf-8")

# Проверим, что синтаксис валиден
import py_compile
py_compile.compile(str(p), doraise=True)
print("compile OK")
PYEOF

echo
echo "import smoke (через manage.py shell -c):"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.menu.generator import MenuGenerator
g = MenuGenerator.__new__(MenuGenerator)
print('has _ensure_veg_fruit_servings:', hasattr(g, '_ensure_veg_fruit_servings'))
"

echo
echo "=========================================="
echo "  MG-304 APPLY v2 DONE  (backup: $BAK)"
echo "=========================================="
