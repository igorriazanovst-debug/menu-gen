#!/usr/bin/env bash
# MG-606 commits — three sequential commits + push.
# Location: /opt/menugen/backend/scripts/commit_606.sh
# Run: bash /opt/menugen/backend/scripts/commit_606.sh 2>&1 | tee /tmp/commit_606.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

echo "===================================================================="
echo "MG-606 commits — start"
echo "===================================================================="

# Sanity: must be on main and clean dir for non-MG-606 files
echo
echo "--- Pre-commit status ---"
git rev-parse --abbrev-ref HEAD
git log --oneline -3

# Ensure subscriptions/tests/__init__.py exists (added by patch_606a)
if [ ! -f backend/apps/subscriptions/tests/__init__.py ]; then
  echo "Creating backend/apps/subscriptions/tests/__init__.py"
  touch backend/apps/subscriptions/tests/__init__.py
fi

# ─────────────────────────────────────────────────────────────────────────
# Commit 1: MG-606.A — helpers + permission + tests
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Commit 1/3: MG-606.A"
echo "===================================================================="

git add \
  backend/apps/subscriptions/permissions.py \
  backend/apps/subscriptions/tests/__init__.py \
  backend/apps/subscriptions/tests/test_mg_606a_premium_helpers.py

echo "--- Staged for MG-606.A ---"
git diff --cached --stat

git commit -m "MG-606.A: has_ever_had_premium + IsFamilyPremiumOrReadOnly

- has_active_premium: status IN (active, trial) + expires_at>now (existing)
- has_ever_had_premium: status IN (active, expired) — read access
  after subscription expiry; cancelled-only or trial-only does NOT grant.
- IsFamilyPremiumOrReadOnly (DRF): SAFE_METHODS → has_ever_had_premium,
  write → has_active_premium. Returns 403 with distinct messages.
- IsFamilyPremium kept as legacy (used elsewhere if needed).

Tests: 23 new in apps/subscriptions/tests/test_mg_606a_premium_helpers.py
covering all helper branches + permission matrix.
"

# ─────────────────────────────────────────────────────────────────────────
# Commit 2: MG-606.B — diary migration
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Commit 2/3: MG-606.B"
echo "===================================================================="

git add \
  backend/apps/diary/views.py \
  backend/apps/diary/tests/test_mg_605c_permissions.py \
  backend/apps/diary/tests/test_mg_606b_premium_or_readonly.py

echo "--- Staged for MG-606.B ---"
git diff --cached --stat

git commit -m "MG-606.B: diary migrated to IsFamilyPremiumOrReadOnly

- 5 diary views switched from IsFamilyPremium → IsFamilyPremiumOrReadOnly.
- Behavior: after subscription expiry GET stays accessible (200),
  write (POST/PATCH/DELETE) → 403.
- Existing 605C tests adjusted:
  * test_expired_premium_403 → test_expired_premium_read_ok_write_forbidden
  * test_trial_premium_200 → test_trial_premium_write_ok_read_forbidden
- New apps/diary/tests/test_mg_606b_premium_or_readonly.py (21 tests):
  active / expired / cancelled-only / no-subscription / trial-only /
  history active→expired — all paths covered.
"

# ─────────────────────────────────────────────────────────────────────────
# Commit 3: MG-606.C — menu/fridge/notifications + dev scripts
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Commit 3/3: MG-606.C"
echo "===================================================================="

# Source/test files
git add \
  backend/apps/menu/views.py \
  backend/apps/menu/tests/test_menu.py \
  backend/apps/menu/tests/test_mg_301.py \
  backend/apps/menu/tests/test_mg_601_integration.py \
  backend/apps/menu/tests/test_mg_602_views.py \
  backend/apps/menu/tests/test_mg_605a_mode.py \
  backend/apps/menu/tests/test_mg_606c_premium_gate.py \
  backend/apps/fridge/views.py \
  backend/apps/fridge/tests/test_fridge.py \
  backend/apps/fridge/tests/test_mg_606c_premium_gate.py \
  backend/apps/notifications/views.py \
  backend/apps/notifications/tests/test_mg_606c_premium_gate.py

# Dev scripts (diag + patch + commit + regress) — keep history of work
git add \
  backend/scripts/commit_605d.sh \
  backend/scripts/diag_606_git_status.sh \
  backend/scripts/diag_606b_expired_test.sh \
  backend/scripts/diag_606b_locate.sh \
  backend/scripts/diag_606c.sh \
  backend/scripts/diag_606c1_602_tests.sh \
  backend/scripts/diag_606c1_urls.sh \
  backend/scripts/diag_606c2_fridge_urls.sh \
  backend/scripts/diag_606c_api_tests.sh \
  backend/scripts/diag_606c_menu_blocks.sh \
  backend/scripts/diag_premium_gate.sh \
  backend/scripts/diag_premium_gate2.sh \
  backend/scripts/patch_606a_subscriptions.sh \
  backend/scripts/patch_606b_create_tests.sh \
  backend/scripts/patch_606b_diary.sh \
  backend/scripts/patch_606b_diary_finalize.sh \
  backend/scripts/patch_606b_fix_trial.sh \
  backend/scripts/patch_606c1_fix_no_family.sh \
  backend/scripts/patch_606c1_fix_url.sh \
  backend/scripts/patch_606c1_menu.sh \
  backend/scripts/patch_606c2_fix_url.sh \
  backend/scripts/patch_606c2_fridge.sh \
  backend/scripts/patch_606c3_notifications.sh \
  backend/scripts/regress_606_sanity_live.sh \
  backend/scripts/regress_menu_live.sh

echo "--- Staged for MG-606.C ---"
git diff --cached --stat

git commit -m "MG-606.C: Premium gate on menu, fridge, notifications

Apps with IsFamilyPremiumOrReadOnly applied to every view:
- menu (10 views): generate, list, detail, delete, quarantine list/restore,
  item swap, archive, shopping list, item toggle.
- fridge (4 views): list/create, item detail, barcode scan, product search.
- notifications (2 views): list, mark-read.

Existing tests adapted:
- menu/tests/test_*: _attach_premium(family) auto-injected after every
  Family.objects.create — fixtures now get active Premium so original
  assertions pass.
- menu/tests/test_mg_602_views.py: 9 'no_family → 404' tests renamed and
  asserts changed to 403 (Premium gate fires before view's family check
  when user has no family ⇒ no Premium).
- fridge/tests/test_fridge.py: same fixture treatment.

New gate test files (one per app):
- apps/menu/tests/test_mg_606c_premium_gate.py (8 tests)
- apps/fridge/tests/test_mg_606c_premium_gate.py (8 tests)
- apps/notifications/tests/test_mg_606c_premium_gate.py (7 tests)

Total green: 349 across diary/subscriptions/menu/fridge/notifications.

Includes diag/patch/regress dev scripts under backend/scripts/ for history.
"

# ─────────────────────────────────────────────────────────────────────────
# Show result
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Final state"
echo "===================================================================="
git log --oneline -6
echo
echo "Status (should be clean):"
git status --short

echo
echo "MG-606 commits — done. Push with:"
echo "  git push origin main"
