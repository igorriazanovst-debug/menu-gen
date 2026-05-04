#!/usr/bin/env bash
set -euo pipefail

DC="docker compose -f /opt/menugen/docker-compose.yml"

echo "### G. FamilyMember serializers — поля ###"
$DC exec -T backend python manage.py shell -c "
from apps.family.serializers import FamilyMemberSerializer
s = FamilyMemberSerializer()
print('FamilyMemberSerializer:')
for n, f in s.get_fields().items():
    print(f'  {n}: {type(f).__name__}')
print()
try:
    from apps.family.serializers import FamilyMemberUpdateSerializer
    s2 = FamilyMemberUpdateSerializer()
    print('FamilyMemberUpdateSerializer:')
    for n, f in s2.get_fields().items():
        print(f'  {n}: {type(f).__name__}')
except Exception as e:
    print(f'NO FamilyMemberUpdateSerializer: {e}')
print()
try:
    from apps.family.serializers import FamilySerializer
    s3 = FamilySerializer()
    print('FamilySerializer:')
    for n, f in s3.get_fields().items():
        print(f'  {n}: {type(f).__name__}')
except Exception as e:
    print(f'NO FamilySerializer: {e}')
"
echo

echo "### G2. Реальный JSON ответа /api/v1/family/ для admin ###"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User
from apps.family.models import Family
from apps.family.serializers import FamilySerializer
import json
u = User.objects.filter(email='admin@dev.local').first()
if u:
    f = Family.objects.filter(members__user=u).first() or Family.objects.first()
    if f:
        s = FamilySerializer(f, context={'request': None})
        print(json.dumps(s.data, ensure_ascii=False, indent=2, default=str))
    else:
        print('NO FAMILY')
else:
    print('NO USER')
"
echo

echo "### H. URL family/users/me ###"
$DC exec -T backend python manage.py shell -c "
from django.urls import get_resolver
r = get_resolver()
def walk(urlpatterns, prefix=''):
    for u in urlpatterns:
        if hasattr(u, 'url_patterns'):
            walk(u.url_patterns, prefix + str(u.pattern))
        else:
            p = prefix + str(u.pattern)
            if 'family' in p or 'users/me' in p:
                cb = getattr(u.callback, '__qualname__', str(u.callback))
                print(f'{p}  ->  {cb}')
walk(r.url_patterns)
"
echo

echo "### I. apps/family/serializers.py — классы и Meta.fields ###"
sed -n '1,200p' /opt/menugen/backend/apps/family/serializers.py
echo
echo "--- остаток ---"
sed -n '200,400p' /opt/menugen/backend/apps/family/serializers.py 2>/dev/null
echo

echo "### J. apps/menu/serializers.py + apps/menu/views.py — есть ли day-summary endpoint? ###"
grep -nE "calorie|nutrition|day_summary|day_nutrition|TotalCalor" /opt/menugen/backend/apps/menu/serializers.py /opt/menugen/backend/apps/menu/views.py 2>/dev/null | head -40
echo

echo "### K. как admin принадлежит к семье (FamilyMember role)? ###"
$DC exec -T backend python manage.py shell -c "
from apps.users.models import User
from apps.family.models import Family, FamilyMember
u = User.objects.filter(email='admin@dev.local').first()
print('user:', u, 'id:', u.id if u else None)
for m in FamilyMember.objects.filter(user=u):
    print(f'  member id={m.id} family={m.family_id} role={m.role}')
print()
print('Все семьи:')
for f in Family.objects.all():
    print(f'  family id={f.id} name={f.name} owner_id={f.owner_id}')
    for m in f.members.all():
        print(f'    member id={m.id} user_id={m.user_id} name={m.user.name} role={m.role}')
"
