#!/usr/bin/env bash
# MG-profile-premium: commit + push.
set -euo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

git status --short
echo
echo "--- staging ---"
git add \
  backend/apps/users/serializers.py \
  backend/apps/users/tests/test_mg_profile_premium.py \
  mobile/menugen_app/lib/core/premium/premium_gate_cubit.dart \
  mobile/menugen_app/lib/core/premium/premium_badge.dart \
  mobile/menugen_app/lib/features/auth/bloc/auth_bloc.dart \
  mobile/menugen_app/lib/main.dart \
  mobile/menugen_app/lib/features/profile/screens/profile_screen.dart \
  mobile/menugen_app/test/premium_gate_cubit_test.dart

git status --short
echo
echo "--- commit ---"
git commit -m "MG-profile-premium: subscription_status on /users/me/ + proactive PremiumGate

Backend:
- UserMeSerializer exposes subscription_status object derived from
  has_active_premium / has_ever_had_premium + latest Subscription row.
- Shape: {is_active_premium, has_ever_premium, plan_code, status, expires_at}
  or null when user has no family.
- 8 tests covering: no-family, no-sub, active, trial, expired, cancelled,
  basic-plan, multi-sub-latest-wins.

Mobile:
- PremiumGateCubit.bootstrap(me) seeds initial state from /users/me/
  payload: active -> unknown, expired-with-history -> lockedForWrite,
  never-paid -> lockedForRead.
- AuthBloc passes me to premiumGate on _onCheck/_onLogin; resets on logout.
- ProfileScreen renders PremiumBadge: green 'Premium until DD.MM.YYYY',
  blue 'Trial until …', orange tappable 'Subscription expired — renew'.
- 5 bloc-tests on bootstrap matrix."

echo
echo "--- push ---"
git push origin "$(git rev-parse --abbrev-ref HEAD)"
echo
echo "DONE. Check CI:"
echo "  https://github.com/$(git remote get-url origin | sed -E 's|.*[:/]([^/]+/[^/.]+)(\.git)?$|\1|')/actions"
