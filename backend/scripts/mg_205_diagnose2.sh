#!/usr/bin/env bash
# MG-205 diagnose part 2 (read-only)
# Запуск: bash /opt/menugen/backend/scripts/mg_205_diagnose2.sh

set -u
PROJECT_ROOT="/opt/menugen"
BACKEND="${PROJECT_ROOT}/backend"
COMPOSE="docker compose -f ${PROJECT_ROOT}/docker-compose.yml"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. apps/specialists — все .py файлы (без .bak)"
ls -la "${BACKEND}/apps/specialists/" | grep -vE '\.bak$|__pycache__'

hr "2. apps/specialists/views.py — какие view + permission_classes"
grep -nE 'class |permission_classes|IsAuthenticated|FamilyHead|Specialist' \
  "${BACKEND}/apps/specialists/views.py" | head -50

hr "3. apps/specialists — есть ли уже permissions.py?"
if [ -f "${BACKEND}/apps/specialists/permissions.py" ]; then
  echo "  YES:"
  cat -n "${BACKEND}/apps/specialists/permissions.py"
else
  echo "  NO"
fi

hr "4. Где ещё лежат permissions.py в проекте?"
find "${BACKEND}/apps" -name "permissions.py" -not -path "*/__pycache__/*"

hr "5. AuditLog model — поля и сигнатура"
grep -nE 'class AuditLog|=\s*models\.|action|entity_type|entity_id|old_values|new_values|user' \
  "${BACKEND}/apps/sync/models.py" 2>/dev/null | head -30

hr "6. apps/specialists/serializers.py — ProfileSerializer? Client API?"
grep -nE 'class |ProfileSerializer|FamilyMember|Profile' \
  "${BACKEND}/apps/specialists/serializers.py" 2>/dev/null | head -30

hr "7. apps/specialists/urls.py — какие роуты"
cat -n "${BACKEND}/apps/specialists/urls.py" 2>/dev/null

hr "8. SpecialistAssignment — поля и status"
grep -nE 'class SpecialistAssignment|=\s*models\.|class Status|class Type' \
  "${BACKEND}/apps/specialists/models.py" 2>/dev/null

hr "9. INSTALLED_APPS (правильно — через manage.py shell)"
${COMPOSE} exec -T backend python manage.py shell -c "
from django.conf import settings
for a in settings.INSTALLED_APPS:
    print(' ', a)
" 2>&1 | grep -E '^\s+(apps\.|django\.contrib\.)' | head -40

hr "10. JSONField sanity (через manage.py shell)"
${COMPOSE} exec -T backend python manage.py shell -c "
from django.db import models, connection
print('  vendor:', connection.vendor)
print('  JSONField:', models.JSONField)
print('  Postgres version:')
with connection.cursor() as c:
    c.execute('SELECT version()')
    print('   ', c.fetchone()[0])
" 2>&1 | tail -15

echo
echo "=== diagnose2 finished ==="
