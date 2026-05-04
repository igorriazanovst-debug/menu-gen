#!/usr/bin/env bash
# MG-201 финальная проверка состояния бэкенда после правок.
set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"

echo "================================================================"
echo "MG-201 FINAL AUDIT — backend"
echo "================================================================"

# 1. Остатки старых имён в backend (исключаем сами скрипты MG-201 и migrations)
echo
echo "[1] Остатки 'carbs_target_g' и 'meal_plan' (без _type) в backend:"

EXCLUDES=(
  --exclude-dir=__pycache__
  --exclude-dir=migrations
  --exclude=mg_201_*.sh
  --exclude=mg_201_*.py
  --exclude=mg201_*
)

found_carbs=$(grep -rEn "${EXCLUDES[@]}" '\bcarbs_target_g\b' "$ROOT/backend" 2>/dev/null || true)
if [[ -z "$found_carbs" ]]; then
  echo "    carbs_target_g: 0 ✅"
else
  echo "    carbs_target_g: НАЙДЕНЫ ⚠️"
  echo "$found_carbs" | sed 's/^/      /'
fi

found_mp=$(grep -rPn "${EXCLUDES[@]}" '\bmeal_plan\b(?!_type)' "$ROOT/backend" 2>/dev/null || true)
if [[ -z "$found_mp" ]]; then
  echo "    meal_plan (без _type): 0 ✅"
else
  echo "    meal_plan (без _type): НАЙДЕНЫ ⚠️"
  echo "$found_mp" | sed 's/^/      /'
fi

# 2. Колонки в БД
echo
echo "[2] Колонки в БД (profiles):"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='profiles' ORDER BY column_name\")
    cols = [r[0] for r in c.fetchall()]
need_present = ['carb_target_g', 'meal_plan_type']
need_absent  = ['carbs_target_g', 'meal_plan']
print('    все колонки:', cols)
for n in need_present:
    print(f'    {n!r}: {\"✅\" if n in cols else \"❌\"}')
for n in need_absent:
    print(f'    отсутствие {n!r}: {\"✅\" if n not in cols else \"❌\"}')
"

# 3. Состояние миграций users
echo
echo "[3] Применённые миграции users:"
docker compose -f "$COMPOSE" exec -T backend python manage.py showmigrations users

# 4. Запись профиля
echo
echo "[4] Запись Profile pid=1:"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.users.models import Profile
p = Profile.objects.first()
if p:
    print(f'    pid={p.id}')
    print(f'    protein_target_g={p.protein_target_g}')
    print(f'    fat_target_g={p.fat_target_g}')
    print(f'    carb_target_g={p.carb_target_g}')
    print(f'    fiber_target_g={p.fiber_target_g}')
    print(f'    meal_plan_type={p.meal_plan_type}')
"

# 5. Smoke серилизатора (если получится найти)
echo
echo "[5] Сериализация Profile через DRF:"
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from apps.users.models import Profile
from apps.users import serializers as S
# попробуем стандартные имена
for name in ('ProfileSerializer','ProfileReadSerializer','ProfileDetailSerializer','UserProfileSerializer'):
    cls = getattr(S, name, None)
    if cls:
        p = Profile.objects.first()
        try:
            data = cls(p).data
            print(f'    {name}: OK')
            for k,v in data.items():
                if 'target' in k or 'meal' in k:
                    print(f'      {k}: {v!r}')
        except Exception as e:
            print(f'    {name}: ошибка {e}')
        break
else:
    print('    (стандартные имена сериализаторов не найдены — пропускаем)')
"

echo
echo "================================================================"
echo "DONE"
echo "================================================================"
