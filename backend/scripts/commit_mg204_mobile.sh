#!/usr/bin/env bash
# Stage, commit and push the MG-204 mobile patch.
# Run from /opt/menugen.
set -euo pipefail

cd /opt/menugen

echo ">>> git status (mobile/)"
git status -s mobile/

echo
echo ">>> git add"
git add mobile/menugen_app/lib mobile/menugen_app/test

echo
echo ">>> git status after add"
git status -s mobile/

echo
echo ">>> commit"
git commit -m "MG-204 mobile: diary plan/fact + import-from-menu + stats; MG-606 premium gate

MG-204-D (diary, follows MG-605.B/C/D):
- DiaryEntry + DiaryDayStats domain models (plain Dart, no freezed)
- DiaryBloc rewrite: load(date+memberId), markEaten, addManual, delete,
  importFromMenu; converted to part-of layout (event/state in part files)
- DiaryScreen rewrite: Plan / Факт sections, checkbox to toggle is_eaten,
  swipe-to-delete, stats card, import-from-menu dialog
- MenuBloc cleaned up (Q1: part-of, removed duplicate inline definitions)

MG-204-P (premium gate, follows MG-606.A/B/C):
- ApiException with isPremiumLocked getter (statusCode==403)
- DioApiClient now throws ApiException on non-2xx and broadcasts
  via errorStream<ApiException>
- PremiumGateCubit: global premium-state tracker (unknown / lockedForRead
  / lockedForWrite), subscribes to errorStream + accepts explicit reports
- Per-bloc *PremiumLocked states (diary/menu/fridge) with isWrite flag
- PaywallBanner shown above MainShell content when locked
- PaywallScreen at /paywall (minimal stub for chat-31; real flow MG-payments)

Tests added/updated:
- diary_bloc_test: load → Loaded with parsed entries; 403 → PremiumLocked;
  generic → Error; markEaten patches /diary/{id}/
- menu_bloc_test: 403 read → MenuPremiumLocked(write=false);
  403 generate → MenuPremiumLocked(write=true)
- fridge_bloc_test: 403 → FridgePremiumLocked
- api_exception_test: status-code classification (premium/network/server)
- premium_gate_cubit_test: stream wiring, reportLock, reportReadSuccess

Out of scope (resume-noted):
- Drift offline cache wiring (AppDatabase is still a stub, schema preserved)
- Notifications feature (separate ticket)
- Real payment flow (PaywallScreen is a stub)
- Profile premium badge (no premium field on /users/me/ yet)"

echo
echo ">>> push"
git push origin main

echo
echo ">>> Head:"
git log --oneline -3
