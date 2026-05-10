#!/usr/bin/env bash
# MG-301 diagnose v3: проверить контракты для apply.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
BACKEND="${PROJECT_ROOT}/backend"

echo "=== MG-301 DIAGNOSE v3 === $(date -Is)"
echo

echo "===== [A] apps/sync/models.py — AuditLog ====="
if [[ -f "${BACKEND}/apps/sync/models.py" ]]; then
    awk '
      /^class AuditLog\b/ { in_a=1 }
      in_a && /^class [A-Z]/ && !/^class AuditLog\b/ { in_a=0 }
      in_a { print NR": "$0 }
    ' "${BACKEND}/apps/sync/models.py"
else
    echo "  ❌ apps/sync/models.py не найден"
fi
echo

echo "===== [B] apps/users/audit.py — record_target_change (как пример вызова AuditLog) ====="
if [[ -f "${BACKEND}/apps/users/audit.py" ]]; then
    cat -n "${BACKEND}/apps/users/audit.py" | head -80
else
    echo "  ❌ apps/users/audit.py не найден"
fi
echo

echo "===== [C] apps/menu/views.py — MenuGenerateView (целиком) ====="
awk '
  /^class MenuGenerateView\b/ { in_v=1 }
  in_v && /^class [A-Z]/ && !/^class MenuGenerateView\b/ { in_v=0 }
  in_v { print NR": "$0 }
' "${BACKEND}/apps/menu/views.py"
echo

echo "===== [D] apps/menu/views.py — _menu_snapshot ====="
awk '
  /^def _menu_snapshot\b/ { in_f=1 }
  in_f && /^[a-zA-Z_]/ && !/^def _menu_snapshot\b/ { if (NR>start) { in_f=0 } }
  in_f { print NR": "$0; start=NR }
' "${BACKEND}/apps/menu/views.py" | head -40
echo

echo "===== [E] apps/recipes/models.py — Recipe (поля + FoodGroup/ProteinType/GrainType) ====="
awk '
  /^class (Recipe|FoodGroup|ProteinType|GrainType)\b/ { in_c=1; print NR": "$0; next }
  in_c && /^class [A-Z]/ { in_c=0 }
  in_c { print NR": "$0 }
' "${BACKEND}/apps/recipes/models.py" | head -120
echo

echo "===== [F] суммарка по food_group в БД ====="
docker compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from collections import Counter
total = Recipe.objects.count()
print('Total recipes:', total)
fg = Counter(Recipe.objects.values_list('food_group', flat=True))
print('food_group distribution:')
for k, v in sorted(fg.items(), key=lambda x: -x[1]):
    print(f'  {k!r}: {v}')
sf_with = Recipe.objects.exclude(suitable_for=[]).count()
print(f'suitable_for filled: {sf_with}/{total}')
" 2>&1 | tail -25 || true
echo

echo "===== [G] что вызывает Menu/MenuItem.objects.create в views (для понимания, как сейчас сохраняется) ====="
grep -nE "(Menu|MenuItem)\.objects\.(create|bulk_create)" "${BACKEND}/apps/menu/views.py" || true
echo

echo "===== [H] существующий conftest.py для тестов menu ====="
find "${BACKEND}" -name "conftest.py" -not -path "*/node_modules/*" | head -10
echo

echo "=== DIAGNOSE v3 DONE ==="
