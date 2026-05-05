#!/bin/bash
# /opt/menugen/scripts/mg_205ui_commit.sh
# Коммит MG-205-UI: backend + web + mobile.
set -euo pipefail

ROOT=/opt/menugen
cd $ROOT

# Бэкапы и логи не коммитим — удостоверимся что .gitignore их игнорирует
if ! grep -qE "^backups/" .gitignore 2>/dev/null; then
  echo "backups/" >> .gitignore
fi

git add -A

git status --short

git commit -m "MG-205-UI: показ источника КБЖУ + история + reset (web + mobile)

Backend (apps/users + apps/family):
- ProfileSerializer.targets_meta — на каждое из 5 target-полей:
  {source, by_user{id,name}|null, at}
- ProfileTargetAuditSerializer + новые endpoint'ы:
  GET  /users/me/targets/{field}/history/
  POST /users/me/targets/{field}/reset/   → пересчёт + source='auto'
  GET  /family/members/{id}/targets/{field}/history/
  POST /family/members/{id}/targets/{field}/reset/
- Validation: bad field → 400 со списком допустимых.
- Permissions для family-ручек: head | self | verified specialist
  с активным assignment.

Web (web/menugen-web):
- types: TargetSource, TargetMeta, TargetsMeta, TargetAuditEntry, TargetField.
- api/users.ts (новый): getTargetHistory, resetTarget.
- api/family.ts: getMemberTargetHistory, resetMemberTarget.
- components/profile/TargetField.tsx — пилюля КБЖУ + бейдж источника
  (auto/вручную/специалист), popover с историей и кнопкой 'Сбросить к авто'.
- ProfilePage и FamilyMemberEditModal используют TargetField вместо
  локальных MacroPill.

Mobile (mobile/menugen_app):
- core/widgets/target_field.dart — TargetField + TargetFieldsRow + два
  loader'а (MeTargetLoader, FamilyMemberTargetLoader) + bottom sheet
  с историей и reset.
- profile_screen.dart, family_screen.dart переключены на TargetFieldsRow.

Smoke (DRF APIClient внутри backend контейнера):
- 8/8 pytest test_mg_205.py → PASSED.
- HTTP 200 на /users/me/, history, PATCH override, reset.
- HTTP 400 на invalid field name с понятным сообщением.
- Source последней правки в targets_meta меняется auto → user → auto.

Markers: MG_205UI_V_*."

git log --oneline -3
