#!/usr/bin/env bash
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"

echo "=========================================="
echo "MG-204 DIAGNOSE-2"
echo "=========================================="
echo

echo "### A. FamilyPage.tsx — целиком ###"
F="$SRC/pages/Family/FamilyPage.tsx"
if [ -f "$F" ]; then
  wc -l "$F"
  echo "--- содержимое ---"
  cat -n "$F"
else
  echo "NO $F"
fi
echo

echo "### B. Поиск любых edit/modal/form компонентов для FamilyMember во всём src/ ###"
grep -rn "FamilyMember" "$SRC" --include="*.tsx" --include="*.ts" 2>/dev/null | head -40
echo
echo "--- файлы с 'family' в имени ---"
find "$SRC" -type f \( -name "*amily*" -o -name "*FAMILY*" \) | sort
echo

echo "### C. types/index.ts — целиком (он маленький, посмотрим всё) ###"
T="$SRC/types/index.ts"
if [ -f "$T" ]; then
  wc -l "$T"
  echo "--- содержимое ---"
  cat -n "$T"
else
  echo "NO $T"
fi
echo

echo "### D. api/family.ts + api/auth.ts — целиком ###"
for f in "$SRC/api/family.ts" "$SRC/api/auth.ts"; do
  if [ -f "$f" ]; then
    echo "--- $f ---"
    cat -n "$f"
    echo
  fi
done

echo "### E. api/ (вся структура, мб есть users.ts отдельно) ###"
ls -la "$SRC/api/" 2>/dev/null
echo
find "$SRC/api" -type f | xargs -I {} echo {}
echo

echo "### F. MenuPage.tsx — структура (только заголовки/импорты + размеры функций) ###"
M="$SRC/pages/Menu/MenuPage.tsx"
if [ -f "$M" ]; then
  wc -l "$M"
  echo "--- импорты + первые 40 строк ---"
  sed -n '1,40p' "$M"
  echo
  echo "--- top-level функции/компоненты (export / function / const ... = ) ---"
  grep -nE "^(export |function |const [A-Z][A-Za-z]+\s*[:=]|interface |type )" "$M"
  echo
  echo "--- где рендерится список дней (поиск day_offset/days/Day) ---"
  grep -nE "day_offset|days\.|<Day|DayCard|MealCard|meal_type|nutrition" "$M" | head -40
fi
echo

echo "### G. Backend: что отдаёт /api/v1/family/members и какие поля в FamilyMember сериализаторе ###"
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python -c "
import json, django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','menugen.settings')
django.setup()
from apps.family.serializers import FamilyMemberSerializer
print('--- FamilyMemberSerializer fields ---')
s = FamilyMemberSerializer()
for name, field in s.get_fields().items():
    print(f'  {name}: {type(field).__name__}')
print()
# Попробуем найти все view/url/serializer в apps/family
" 2>&1 | head -40
echo

echo "### H. Backend URL'ы family ###"
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py show_urls 2>/dev/null | grep -E "family|users/me" | head -30 || \
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend python -c "
from django.urls import get_resolver
r = get_resolver()
def walk(urlpatterns, prefix=''):
    for u in urlpatterns:
        if hasattr(u, 'url_patterns'):
            walk(u.url_patterns, prefix + str(u.pattern))
        else:
            p = prefix + str(u.pattern)
            if 'family' in p or 'users/me' in p:
                print(p)
walk(r.url_patterns)
" 2>&1 | head -40
echo

echo "### I. apps/family/serializers.py — список полей в каждом сериализаторе ###"
grep -nE "^class |fields = |Meta:" /opt/menugen/backend/apps/family/serializers.py 2>/dev/null | head -60
echo

echo "### J. Проверка fact-of-day API: есть ли backend endpoint, отдающий суммарные КБЖУ за день меню ###"
grep -rnE "calorie|nutrition.*day|day_nutrition|day_summary" /opt/menugen/backend/apps/menu/serializers.py /opt/menugen/backend/apps/menu/views.py 2>/dev/null | head -30
echo

echo "=========================================="
echo "DIAGNOSE-2 END"
echo "=========================================="
