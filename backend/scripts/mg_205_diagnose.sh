#!/usr/bin/env bash
# MG-205 diagnose (read-only): источник правок КБЖУ (auto/user/specialist)
# Запуск: bash /opt/menugen/backend/scripts/mg_205_diagnose.sh

set -u
PROJECT_ROOT="/opt/menugen"
BACKEND="${PROJECT_ROOT}/backend"
COMPOSE="docker compose -f ${PROJECT_ROOT}/docker-compose.yml"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. Profile model — поля, связанные с КБЖУ"
grep -nE 'class Profile|calorie_target|protein_target_g|fat_target_g|carb_target_g|fiber_target_g|meal_plan_type|targets_meta|def save|fill_profile_targets' \
  "${BACKEND}/apps/users/models.py" || echo "  (matches not found)"

hr "2. Миграции apps/users"
ls -1 "${BACKEND}/apps/users/migrations/" 2>/dev/null | grep -v __pycache__

hr "3. apps/specialists — существует?"
if [ -d "${BACKEND}/apps/specialists" ]; then
  echo "  YES → структура:"
  ls -la "${BACKEND}/apps/specialists/"
  echo
  echo "  --- models.py:"
  grep -nE 'class |fields\.|ForeignKey|ManyToMany' "${BACKEND}/apps/specialists/models.py" 2>/dev/null || echo "  (no models.py)"
else
  echo "  NO → нужно создавать с нуля"
fi

hr "4. audit_log — есть в проекте?"
echo "  --- grep по apps/:"
grep -rnE 'class\s+AuditLog|audit_log|AuditEntry' "${BACKEND}/apps/" 2>/dev/null | head -20 || echo "  (not found)"
echo
echo "  --- INSTALLED_APPS:"
grep -nE "INSTALLED_APPS|apps\." "${BACKEND}/menugen/settings.py" 2>/dev/null | head -30 || \
  find "${BACKEND}" -name "settings.py" -path "*/menugen/*" -exec grep -nE 'INSTALLED_APPS|apps\.' {} \; | head -30

hr "5. apps/family/permissions.py"
if [ -f "${BACKEND}/apps/family/permissions.py" ]; then
  cat -n "${BACKEND}/apps/family/permissions.py"
else
  echo "  (отсутствует)"
fi

hr "6. apps/users/views.py — UserMeView и связанные"
grep -nE 'class |permission_classes|UpdateAPIView|RetrieveUpdateAPIView' \
  "${BACKEND}/apps/users/views.py" 2>/dev/null | head -30

hr "7. nutrition.fill_profile_targets — текущая сигнатура"
grep -nE 'def fill_profile_targets|force=|MG_202_V|targets_meta' \
  "${BACKEND}/apps/users/nutrition.py" 2>/dev/null | head -20

hr "8. JSONField — доступен на текущем backend (Postgres)?"
${COMPOSE} exec -T backend python -c "
import django
django.setup()
from django.db import models, connection
print('  django :', django.get_version())
print('  vendor :', connection.vendor)
print('  JSONField available:', hasattr(models, 'JSONField'))
" 2>&1 | tail -10

hr "9. Текущие профили — кто и какие targets имеет"
${COMPOSE} exec -T backend python manage.py shell -c "
from apps.users.models import Profile
qs = Profile.objects.all()
print(f'  total profiles: {qs.count()}')
for p in qs:
    print(f'  pid={p.id} uid={p.user_id} cal={p.calorie_target} P={p.protein_target_g} F={p.fat_target_g} C={p.carb_target_g} Fb={p.fiber_target_g}')
" 2>&1 | tail -20

hr "10. ProfileTargetAudit / targets_meta — уже есть?"
grep -rnE 'ProfileTargetAudit|targets_meta' "${BACKEND}/apps/" 2>/dev/null || echo "  (not found — чисто)"

hr "11. Миграции — последние 5"
${COMPOSE} exec -T backend python manage.py showmigrations users family 2>&1 | tail -20

hr "12. Структура apps/ верхним уровнем"
ls -1 "${BACKEND}/apps/"

echo
echo "=== diagnose finished ==="
