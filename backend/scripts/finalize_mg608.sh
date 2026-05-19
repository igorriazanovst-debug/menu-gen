#!/usr/bin/env bash
# MG-608 finalize: web build → web-dist, restart celery, git commit+push (триггерит mobile CI).
# Запуск:
#   bash /opt/menugen/backend/scripts/finalize_mg608.sh 2>&1 | tee /tmp/finalize_mg608.log

set -euo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
WEB="${ROOT}/web/menugen-web"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── 1. WEB build ───────────────────────────────────────────────────────
hr "1. WEB build"
cd "${WEB}"
CI=false npm run build 2>&1 | tail -15

if [ ! -d "${WEB}/build" ]; then
  echo "✗ build не создан — STOP"
  exit 1
fi

rm -rf /opt/menugen/web-dist
mkdir -p /opt/menugen/web-dist
cp -a "${WEB}/build/." /opt/menugen/web-dist/
echo "✓ web-dist обновлён"
cd "${ROOT}"

# ─── 2. Restart celery + celery-beat ───────────────────────────────────
hr "2. Restart celery / celery-beat"
$COMPOSE restart celery celery-beat 2>&1 | tail -5
sleep 4
echo
echo "--- beat schedule (последние 20 строк логов) ---"
$COMPOSE logs --tail 30 celery-beat 2>&1 | grep -E "purge-expired-menus|Scheduler|beat" | tail -10 || true

# ─── 3. Git status / what we're committing ────────────────────────────
hr "3. Git status"
git -C "${ROOT}" status --short

hr "4. Git diff stat"
git -C "${ROOT}" diff --stat

# ─── 5. commit + push ──────────────────────────────────────────────────
hr "5. commit + push"
cd "${ROOT}"
git add backend/apps/menu/tasks.py \
        backend/apps/menu/views.py \
        backend/apps/menu/urls.py \
        backend/config/settings.py \
        backend/apps/menu/tests/test_mg_608_quarantine.py \
        web/menugen-web/src/api/menu.ts \
        web/menugen-web/src/pages/Menu/MenuPage.tsx \
        mobile/menugen_app/lib/features/menu/bloc/menu_bloc.dart \
        mobile/menugen_app/lib/features/menu/bloc/menu_event.dart \
        mobile/menugen_app/lib/features/menu/bloc/menu_state.dart \
        mobile/menugen_app/lib/features/menu/screens/menu_screen.dart \
        mobile/menugen_app/lib/features/menu/screens/quarantine_screen.dart 2>&1 || true

git status --short

git commit -m "MG-608: menu picker + full quarantine ops

Backend:
- DeletedMenuListView filters expired records (purge_after >= now)
- MenuRestoreView returns 403 for expired records
- MenuPurgeView (DELETE /menu/quarantine/<id>/purge/) — one record
- MenuPurgeAllView (DELETE /menu/quarantine/purge-all/) — wipe all (admin/head)
- apps/menu/tasks.py: purge_expired_menus celery task
- CELERY_BEAT_SCHEDULE += purge-expired-menus (daily 03:15)
- tests: 10/10 PASSED, regress 227/227 PASSED

Web:
- MenuPage.tsx: horizontal chips for menu picker
- localStorage 'menugen.lastMenuId' for last selected
- Quarantine modal: list + restore + delete-forever + clear-all
- api/menu.ts: purge / purgeAll

Mobile:
- MenuDetailRequested event for picking menu by id
- MenuLoaded.menus now full list, .active is detail
- shared_preferences 'menugen.lastMenuId' for last selected
- menu_screen.dart: DropdownButton in AppBar + Карантин action
- quarantine_screen.dart: list + restore + purge + purge-all" 2>&1 | tail -20 || echo "(nothing to commit)"

git push origin main 2>&1 | tail -10 || echo "(push failed or up to date)"

# ─── 6. Mobile CI ──────────────────────────────────────────────────────
hr "6. Mobile CI"
if command -v gh >/dev/null 2>&1; then
  sleep 3
  RUN_ID=$(gh run list --repo igorriazanovst-debug/menu-gen --branch main --workflow flutter_ci.yml --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
  if [ -n "${RUN_ID:-}" ]; then
    echo "RUN_ID=$RUN_ID — стартовал; следить:"
    echo "  gh run watch --repo igorriazanovst-debug/menu-gen $RUN_ID --exit-status"
  else
    echo "(не удалось получить RUN_ID)"
  fi
else
  echo "(gh не установлен, пропускаю)"
fi

hr "7. final HEAD"
git -C "${ROOT}" log --oneline -3

echo
echo "=== MG-608 FINALIZE DONE ==="
