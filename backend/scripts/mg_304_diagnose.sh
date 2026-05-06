#!/bin/bash
# MG-304 — диагностика перед применением правок (5 порций овощей/фруктов в день)
# Запуск на сервере: bash /opt/menugen/backend/scripts/mg_304_diagnose.sh
set -uo pipefail

ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"

echo "=========================================="
echo "  MG-304 DIAGNOSE  $(date '+%F %T')"
echo "=========================================="

echo
echo "--- [1] Окружение ---"
docker compose -f "$COMPOSE" ps --status=running 2>/dev/null | sed -n '1,20p'
echo
echo "PG creds (из контейнера, не хардкод):"
docker compose -f "$COMPOSE" exec -T db sh -c 'echo POSTGRES_USER=$POSTGRES_USER; echo POSTGRES_DB=$POSTGRES_DB' || echo "  (db не доступен)"

echo
echo "--- [2] Файлы, которые трогаем ---"
for f in \
  "$BACKEND/apps/menu/generator.py" \
  "$BACKEND/apps/menu/views.py" \
  "$BACKEND/apps/menu/models.py" \
  "$BACKEND/apps/menu/serializers.py" \
  "$BACKEND/apps/menu/exceptions.py" \
  "$BACKEND/apps/menu/tests/test_mg_301.py"; do
  if [ -f "$f" ]; then
    printf "OK  %s  (%d lines)\n" "$f" "$(wc -l < "$f")"
  else
    printf "MISS %s\n" "$f"
  fi
done

echo
echo "--- [3] Существующие маркеры MG_*_V_* ---"
grep -rnE "MG_30[1-4]_V_|MG_304_V_" \
  --include='*.py' "$BACKEND/apps/menu/" 2>/dev/null \
  | sed 's|^|  |' || echo "  (нет)"

echo
echo "--- [4] Текущие миграции apps/menu ---"
ls -1 "$BACKEND/apps/menu/migrations/" 2>/dev/null | grep -E '^00' || echo "  (нет)"
echo
echo "showmigrations menu:"
docker compose -f "$COMPOSE" exec -T backend python manage.py showmigrations menu 2>/dev/null

echo
echo "--- [5] Поле Menu.warnings — есть ли? ---"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell <<'PYEOF'
from apps.menu.models import Menu
fields = {f.name for f in Menu._meta.get_fields()}
print(f"  Menu.warnings field present: {'warnings' in fields}")
print(f"  All Menu fields: {sorted(fields)}")
PYEOF

echo
echo "--- [6] MEAL_COMPONENTS / MEAL_PLAN_3 / MEAL_PLAN_5 — текущая раскладка ---"
docker compose -f "$COMPOSE" exec -T backend python -c "
from apps.menu.generator import MEAL_COMPONENTS, MEAL_PLAN_3, MEAL_PLAN_5, MEAL_TYPE_DB
print('MEAL_PLAN_3:', MEAL_PLAN_3)
print('MEAL_PLAN_5:', MEAL_PLAN_5)
print('MEAL_TYPE_DB:', MEAL_TYPE_DB)
for k, v in MEAL_COMPONENTS.items():
    print(f'  {k:10s} -> {v}')
"

echo
echo "--- [7] Recipe.nutrition.weight — заполненность ---"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell <<'PYEOF'
from apps.recipes.models import Recipe
from collections import Counter

stats = Counter()
src_examples = {"nutrition_weight": [], "povar_dw": [], "no_weight": []}

qs = Recipe.objects.filter(food_group__in=["vegetable", "fruit"]).only(
    "id", "title", "food_group", "nutrition", "povar_raw", "servings_normalized", "servings"
)
total = qs.count()
for r in qs.iterator():
    nut = r.nutrition or {}
    w = (nut.get("weight") or {}).get("value") if isinstance(nut.get("weight"), dict) else nut.get("weight")
    has_nw = False
    try:
        if w not in (None, "", 0):
            float(str(w).replace(",", "."))
            has_nw = True
    except Exception:
        pass

    pr = r.povar_raw or {}
    dw = pr.get("dish_weight_g_calc")
    sn = r.servings_normalized or r.servings or 1
    has_pdw = bool(dw and sn)

    if has_nw:
        stats["nutrition_weight"] += 1
        if len(src_examples["nutrition_weight"]) < 3:
            src_examples["nutrition_weight"].append((r.id, r.title[:40], w))
    elif has_pdw:
        stats["povar_dw"] += 1
        if len(src_examples["povar_dw"]) < 3:
            src_examples["povar_dw"].append((r.id, r.title[:40], dw, sn))
    else:
        stats["no_weight"] += 1
        if len(src_examples["no_weight"]) < 3:
            src_examples["no_weight"].append((r.id, r.title[:40]))

print(f"vegetable+fruit рецептов: {total}")
print(f"  nutrition.weight:       {stats['nutrition_weight']}")
print(f"  povar_raw.dish_weight:  {stats['povar_dw']}")
print(f"  без веса (default):     {stats['no_weight']}")
print()
print("Примеры по источникам:")
for k, exs in src_examples.items():
    print(f"  [{k}]")
    for ex in exs:
        print(f"    {ex}")
PYEOF

echo
echo "--- [8] FamilyMember -> Profile.birth_year (на каких членах данные есть) ---"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell <<'PYEOF'
from apps.family.models import FamilyMember
total = FamilyMember.objects.count()
with_by = FamilyMember.objects.exclude(user__profile__birth_year__isnull=True).count()
print(f"  members total: {total}, with birth_year: {with_by}")
for m in FamilyMember.objects.select_related("user__profile")[:5]:
    by = getattr(getattr(m.user, "profile", None), "birth_year", None)
    print(f"    member_id={m.id} user={m.user.email or m.user.id} birth_year={by}")
PYEOF

echo
echo "--- [9] Существующие тесты MG-301 ---"
ls -la "$BACKEND/apps/menu/tests/" 2>/dev/null
echo "Запуск pytest -k mg_301 (быстрая проверка что зелёное):"
docker compose -f "$COMPOSE" exec -T backend pytest apps/menu/tests/test_mg_301.py -q 2>&1 | tail -15

echo
echo "=========================================="
echo "  DIAGNOSE END"
echo "=========================================="
