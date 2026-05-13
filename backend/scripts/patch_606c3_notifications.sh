#!/usr/bin/env bash
# MG-606.C.3 — Premium gate on notifications/views.py + gate tests.
# Location: /opt/menugen/backend/scripts/patch_606c3_notifications.sh
# Run: bash /opt/menugen/backend/scripts/patch_606c3_notifications.sh 2>&1 | tee /tmp/patch_606c3_notifications.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BAKDIR="${ROOT}/backups/606c3_${TS}"
mkdir -p "$BAKDIR"

echo "===================================================================="
echo "PATCH-606.C.3 (notifications) — start ($TS)"
echo "===================================================================="

# ─────────────────────────────────────────────────────────────────────────
# 1) views: add IsFamilyPremiumOrReadOnly to both notifications views
# ─────────────────────────────────────────────────────────────────────────
cp "${BACKEND}/apps/notifications/views.py" "$BAKDIR/notifications_views.py.bak"

python3 <<'PYEOF'
VIEWS = "/opt/menugen/backend/apps/notifications/views.py"
src = open(VIEWS).read()

# 1.1 Add import after `from .models import Notification`
old_imp = "from .models import Notification"
new_imp = (
    "from .models import Notification\n"
    "from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly"
)
assert old_imp in src, "missing 'from .models import Notification'"
if "IsFamilyPremiumOrReadOnly" not in src:
    src = src.replace(old_imp, new_imp, 1)

# 1.2 Replace permission_classes lines
old_pc = "permission_classes = [permissions.IsAuthenticated]"
new_pc = "permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]"
count = src.count(old_pc)
assert count == 2, f"expected 2 matches, found {count}"
src = src.replace(old_pc, new_pc)
open(VIEWS, "w").write(src)
print(f"✓ notifications/views.py: {count}/2 permission_classes + import")
PYEOF

echo
echo "--- notifications/views.py permission_classes after patch ---"
grep -n "permission_classes" "${BACKEND}/apps/notifications/views.py"

# ─────────────────────────────────────────────────────────────────────────
# 2) New gate test file
# ─────────────────────────────────────────────────────────────────────────
cat > "${BACKEND}/apps/notifications/tests/test_mg_606c_premium_gate.py" <<'PYEOF'
"""MG-606.C: Premium gate on notifications API.

Endpoints:
- GET  /api/v1/notifications/               — list
- POST /api/v1/notifications/{id}/read/     — mark-read

Coverage:
- no premium → 403 on both
- active premium → 200 list, 200 mark-read
- expired (active+date past) → 200 list, 403 mark-read
- cancelled-only → 403 on both
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.notifications.models import Notification
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _user(email="m@e.com"):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family():
    head = _user()
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _plan():
    p, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return p


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family, plan=_plan(), status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _notif(user):
    return Notification.objects.create(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title="t",
        message="m",
    )


def _auth(c, u):
    c.force_authenticate(u)
    return c


@pytest.mark.django_db
class TestNotificationsPremiumGate:
    def test_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 403

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 200

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 200

    def test_list_cancelled_only_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.CANCELLED)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/notifications/").status_code == 403

    def test_mark_read_no_premium_403(self, db):
        family, head = _family()
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 403

    def test_mark_read_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 200

    def test_mark_read_expired_premium_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        n = _notif(head)
        c = _auth(APIClient(), head)
        assert c.post(f"/api/v1/notifications/{n.id}/read/").status_code == 403
PYEOF
echo "✓ created apps/notifications/tests/test_mg_606c_premium_gate.py"

# ─────────────────────────────────────────────────────────────────────────
# 3) Determine mark-read URL (might differ; verify before running)
# ─────────────────────────────────────────────────────────────────────────
echo
echo "--- notifications/urls.py ---"
cat -n "${BACKEND}/apps/notifications/urls.py"

# ─────────────────────────────────────────────────────────────────────────
# 4) Run tests
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "MG-606.C notifications gate"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/notifications/tests/test_mg_606c_premium_gate.py -v --tb=short

echo
echo "===================================================================="
echo "Regression notifications (incl. Celery tasks)"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/notifications/ -v --tb=short

echo
echo "===================================================================="
echo "Sanity: diary + subscriptions + menu + fridge"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/diary/ apps/subscriptions/ apps/menu/ apps/fridge/ --tb=short 2>&1 | tail -10

echo
echo "PATCH-606.C.3 (notifications) — done"
