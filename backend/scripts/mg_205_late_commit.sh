#!/usr/bin/env bash
# Докоммит MG-205: всё, что осталось незакоммиченным после прошлого чата.
set -euo pipefail
cd /opt/menugen

echo "=========================================="
echo "MG-205 LATE COMMIT"
echo "=========================================="
echo

echo "### 1. Перенос .bak из корня → backups/ ###"
shopt -s nullglob
moved=0
for f in /opt/menugen/MenuGen_Backlog.xlsx.bak_* /opt/menugen/*.bak_*; do
  [ -f "$f" ] || continue
  mv "$f" /opt/menugen/backups/
  echo "  → /opt/menugen/backups/$(basename "$f")"
  moved=$((moved+1))
done
echo "  итого перенесено: $moved"
echo

echo "### 2. git status (короткий) ###"
git status --short
echo

echo "### 3. Добавляем все MG-205 файлы ###"
git add \
  backend/apps/family/serializers.py \
  backend/apps/family/views.py \
  backend/apps/specialists/views.py \
  backend/apps/specialists/permissions.py \
  backend/apps/users/models.py \
  backend/apps/users/nutrition.py \
  backend/apps/users/serializers.py \
  backend/apps/users/audit.py \
  backend/apps/users/migrations/0004_profiletargetaudit.py \
  backend/apps/users/tests/test_mg_205.py \
  backend/scripts/mg_205_*.sh \
  backend/scripts/mg_205_*.py \
  backend/scripts/mg_204_fix_gitignore.sh \
  backend/scripts/mg_204_fix_gitignore_2.sh
# tests/__init__.py если новый — добавим тоже (без ошибки если нет)
if [ -f backend/apps/users/tests/__init__.py ]; then
  git add backend/apps/users/tests/__init__.py 2>/dev/null || true
fi
echo

echo "### 4. Что в индексе ###"
git status --short
echo

echo "### 5. Commit ###"
git commit -m "MG-205: track source of nutrition target edits (auto/user/specialist)

- ProfileTargetAudit model + migration 0004
- apps/users/audit.py: record_target_change/get_field_source/is_locked
- nutrition.fill_profile_targets respects lock from last audit source
- Profile.save() audits on create + accepts _mg205_actor kwarg
- specialists/permissions.py: IsVerifiedSpecialist + SpecialistCanEditClientProfile
  + is_verified_specialist_for_user
- users/serializers + family/serializers write audit on PATCH (source='user' or 'specialist')
- family.views.FamilyMemberUpdateView allows verified specialist with active assignment
- AuditLog dublication with entity_type='profile_target'
- 8 pytest scenarios (auto/user/specialist override/reset/lock/history)

(late-committed in MG-204 chat)"
echo
echo "✅ Done. Последние 4 коммита:"
git log --oneline -4
echo
echo "### 6. git status (должен быть чистым по MG-205) ###"
git status --short
