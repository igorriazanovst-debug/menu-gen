#!/bin/bash
# MG-304 apply v3: вставляем _ensure_veg_fruit_servings (если ОПРЕДЕЛЕНИЯ нет).
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="$ROOT/docker-compose.yml"
MENU="$BACKEND/apps/menu"
F="$MENU/generator.py"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_304_v3_backup_${TS}"

mkdir -p "$BAK"
cp -v "$F" "$BAK/generator.py"
echo "Backup -> $BAK"

python3 - "$F" <<'PYEOF'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); src = p.read_text(encoding="utf-8")

# 1) Проверяем, есть ли само ОПРЕДЕЛЕНИЕ метода
if re.search(r"^[ \t]+def _ensure_veg_fruit_servings\(", src, re.MULTILINE):
    print("SKIP: метод уже определён"); sys.exit(0)

helper = '''    # ── MG-304: добор порций овощей/фруктов ──────────────────────────────────
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

# 2) Вставляем перед "    # ── pools"
marker = "    # ── pools"
if marker not in src:
    print("FATAL: не нашёл маркер '# ── pools'", file=sys.stderr); sys.exit(1)

src = src.replace(marker, helper + marker, 1)
p.write_text(src, encoding="utf-8")

# 3) compile-check
import py_compile
py_compile.compile(str(p), doraise=True)
print("OK: метод вставлен, compile OK")
PYEOF

echo
echo "=== verify через manage.py shell -c ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.menu.generator import MenuGenerator
print('hasattr:', hasattr(MenuGenerator, '_ensure_veg_fruit_servings'))
print('source line:')
import inspect
src, ln = inspect.getsourcelines(MenuGenerator._ensure_veg_fruit_servings)
print(f'  starts at line {ln}, length {len(src)} lines')
"

echo
echo "=== pytest MG-304 ==="
docker compose -f "$COMPOSE" exec -T backend pytest apps/menu/tests/test_mg_304.py -q 2>&1 | tail -25

echo "=========================================="
echo "  MG-304 v3 DONE  (backup: $BAK)"
