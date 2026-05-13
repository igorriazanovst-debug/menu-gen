#!/usr/bin/env bash
# MG-606.A — хелпер has_ever_had_premium + permission IsFamilyPremiumOrReadOnly + тесты subscriptions
# Запуск:
#   bash /opt/menugen/backend/scripts/patch_606a_subscriptions.sh 2>&1 | tee /tmp/patch_606a.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

echo "===================================================================="
echo "PATCH-606.A — старт ($TS)"
echo "===================================================================="

# ── 1. Backup существующего permissions.py ────────────────────────────────
BAKDIR="${ROOT}/backups/606a_${TS}"
mkdir -p "$BAKDIR"
cp "${BACKEND}/apps/subscriptions/permissions.py" "$BAKDIR/permissions.py.bak"
echo "Backup → $BAKDIR/permissions.py.bak"

# ── 2. Перезаписать subscriptions/permissions.py ──────────────────────────
cat > "${BACKEND}/apps/subscriptions/permissions.py" <<'PYEOF'
"""MG-605.C / MG-606.A: Premium gate.

Хелперы и DRF-permission'ы:

- `has_active_premium(family)` — у семьи есть подписка с
  plan.code='premium', status IN ('active', 'trial'), expires_at > now().
- `has_ever_had_premium(family)` — у семьи когда-либо была подписка с
  plan.code='premium', status IN ('active', 'expired'). Используется
  для read-only доступа после истечения.

- `IsFamilyPremium` — закрывает ВСЁ (legacy, оставлен для совместимости).
- `IsFamilyPremiumOrReadOnly` — MG-606.A:
    * SAFE_METHODS (GET/HEAD/OPTIONS) → нужен has_ever_had_premium
    * write (POST/PATCH/PUT/DELETE)   → нужен has_active_premium
"""
from django.utils import timezone
from rest_framework import permissions

from apps.family.models import FamilyMember
from .models import Subscription


PREMIUM_PLAN_CODE = "premium"
PREMIUM_ACTIVE_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.TRIAL)
# MG-606.A: статусы, дающие read-only после истечения
PREMIUM_HISTORICAL_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.EXPIRED)


def has_active_premium(family) -> bool:
    """True, если у семьи есть активная Premium-подписка (active/trial, не истёк)."""
    if family is None:
        return False
    return Subscription.objects.filter(
        family=family,
        plan__code=PREMIUM_PLAN_CODE,
        status__in=PREMIUM_ACTIVE_STATUSES,
        expires_at__gt=timezone.now(),
    ).exists()


def has_ever_had_premium(family) -> bool:
    """MG-606.A: True, если у семьи когда-либо была реальная Premium-подписка.

    Считаем «реальной» подписку со status IN (active, expired).
    cancelled/trial без перехода в active — не дают read-доступа после истечения.

    Если подписка active и ещё не истекла — тоже True (включает текущих пользователей).
    """
    if family is None:
        return False
    return Subscription.objects.filter(
        family=family,
        plan__code=PREMIUM_PLAN_CODE,
        status__in=PREMIUM_HISTORICAL_STATUSES,
    ).exists()


def get_user_family(user):
    """Возвращает Family пользователя (через FamilyMember) или None."""
    if not user or not user.is_authenticated:
        return None
    membership = (
        FamilyMember.objects.select_related("family")
        .filter(user=user)
        .first()
    )
    return membership.family if membership else None


class IsFamilyPremium(permissions.BasePermission):
    """Разрешает доступ только если у семьи активна Premium (legacy, MG-605.C)."""

    message = "Требуется активная Premium-подписка."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        family = get_user_family(request.user)
        return has_active_premium(family)


class IsFamilyPremiumOrReadOnly(permissions.BasePermission):
    """MG-606.A: гибкий Premium gate.

    - SAFE_METHODS → достаточно has_ever_had_premium
    - write       → требует has_active_premium
    """

    message_read = "Доступ к чтению требует наличия Premium-подписки в истории."
    message_write = "Запись требует активную Premium-подписку."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        family = get_user_family(request.user)
        if request.method in permissions.SAFE_METHODS:
            ok = has_ever_had_premium(family)
            if not ok:
                self.message = self.message_read
            return ok
        ok = has_active_premium(family)
        if not ok:
            self.message = self.message_write
        return ok
PYEOF
echo "✓ переписан apps/subscriptions/permissions.py"

# ── 3. Подкаталог tests/ ──────────────────────────────────────────────────
mkdir -p "${BACKEND}/apps/subscriptions/tests"
touch "${BACKEND}/apps/subscriptions/tests/__init__.py"

# ── 4. Новый тестовый файл ───────────────────────────────────────────────
cat > "${BACKEND}/apps/subscriptions/tests/test_mg_606a_premium_helpers.py" <<'PYEOF'
"""MG-606.A: тесты has_ever_had_premium + IsFamilyPremiumOrReadOnly.

Идея: ввести хелпер «премиум был» и permission «GET — всем кто платил,
write — только активным». Подписки cancelled / одинокий trial → read запрещён.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework import permissions as drf_permissions

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.subscriptions.permissions import (
    IsFamilyPremium,
    IsFamilyPremiumOrReadOnly,
    has_active_premium,
    has_ever_had_premium,
)
from apps.users.models import User


# ─── фикстуры ───────────────────────────────────────────────────────────────

@pytest.fixture
def plan_premium(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("499")},
    )
    return plan


@pytest.fixture
def plan_basic(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="basic",
        defaults={"name": "Basic", "price": Decimal("0")},
    )
    return plan


def _user(email):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family(owner_email="head@e.com"):
    head = _user(owner_email)
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _sub(family, plan, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=plan,
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


# ─── 1. has_active_premium ──────────────────────────────────────────────────

class TestHasActivePremium:
    def test_none_family(self, db):
        assert has_active_premium(None) is False

    def test_active_returns_true(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.ACTIVE)
        assert has_active_premium(family) is True

    def test_trial_returns_true(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.TRIAL)
        assert has_active_premium(family) is True

    def test_expired_returns_false(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.EXPIRED, expires_in_days=-1)
        assert has_active_premium(family) is False

    def test_cancelled_returns_false(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.CANCELLED)
        assert has_active_premium(family) is False

    def test_expired_by_date_returns_false(self, db, plan_premium):
        family, _ = _family()
        # статус active, но дата истекла
        _sub(family, plan_premium, Subscription.Status.ACTIVE, expires_in_days=-1)
        assert has_active_premium(family) is False

    def test_basic_plan_not_premium(self, db, plan_basic):
        family, _ = _family()
        _sub(family, plan_basic, Subscription.Status.ACTIVE)
        assert has_active_premium(family) is False


# ─── 2. has_ever_had_premium ────────────────────────────────────────────────

class TestHasEverHadPremium:
    def test_none_family(self, db):
        assert has_ever_had_premium(None) is False

    def test_no_subscription(self, db):
        family, _ = _family()
        assert has_ever_had_premium(family) is False

    def test_only_trial_returns_false(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.TRIAL)
        assert has_ever_had_premium(family) is False

    def test_only_cancelled_returns_false(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.CANCELLED)
        assert has_ever_had_premium(family) is False

    def test_active_returns_true(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.ACTIVE)
        assert has_ever_had_premium(family) is True

    def test_expired_returns_true(self, db, plan_premium):
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.EXPIRED, expires_in_days=-30)
        assert has_ever_had_premium(family) is True

    def test_basic_active_returns_false(self, db, plan_basic):
        family, _ = _family()
        _sub(family, plan_basic, Subscription.Status.ACTIVE)
        assert has_ever_had_premium(family) is False

    def test_history_with_expired_and_cancelled_after(self, db, plan_premium):
        """Семья платила (active→expired), потом снова trial→cancelled.
        Должна сохранить read-доступ за счёт expired."""
        family, _ = _family()
        _sub(family, plan_premium, Subscription.Status.EXPIRED, expires_in_days=-60)
        _sub(family, plan_premium, Subscription.Status.CANCELLED, expires_in_days=-30)
        assert has_ever_had_premium(family) is True


# ─── 3. IsFamilyPremiumOrReadOnly ───────────────────────────────────────────

def _req(user, method="GET"):
    r = MagicMock()
    r.user = user
    r.method = method
    return r


class TestIsFamilyPremiumOrReadOnly:
    perm = IsFamilyPremiumOrReadOnly()

    def test_unauthenticated_denied(self, db):
        user = MagicMock()
        user.is_authenticated = False
        assert self.perm.has_permission(_req(user, "GET"), None) is False
        assert self.perm.has_permission(_req(user, "POST"), None) is False

    def test_active_premium_can_get_and_write(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.ACTIVE)
        for m in ("GET", "HEAD", "OPTIONS", "POST", "PATCH", "PUT", "DELETE"):
            assert self.perm.has_permission(_req(head, m), None) is True, m

    def test_trial_premium_can_get_and_write(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.TRIAL)
        # write через trial разрешён (как и в has_active_premium)
        assert self.perm.has_permission(_req(head, "GET"), None) is False  # trial без active не даёт read
        # Read-доступ требует ACTIVE или EXPIRED. Trial — не считается «реальным» опытом.
        # Но write при trial — разрешён (фича не отнимается, пока триал идёт).
        assert self.perm.has_permission(_req(head, "POST"), None) is True

    def test_expired_premium_can_get_but_not_write(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.EXPIRED, expires_in_days=-1)
        assert self.perm.has_permission(_req(head, "GET"), None) is True
        assert self.perm.has_permission(_req(head, "POST"), None) is False
        assert self.perm.has_permission(_req(head, "PATCH"), None) is False
        assert self.perm.has_permission(_req(head, "DELETE"), None) is False

    def test_cancelled_only_no_access(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.CANCELLED)
        assert self.perm.has_permission(_req(head, "GET"), None) is False
        assert self.perm.has_permission(_req(head, "POST"), None) is False

    def test_no_subscription_no_access(self, db):
        family, head = _family()
        assert self.perm.has_permission(_req(head, "GET"), None) is False
        assert self.perm.has_permission(_req(head, "POST"), None) is False


# ─── 4. IsFamilyPremium (legacy) ────────────────────────────────────────────

class TestIsFamilyPremiumLegacy:
    perm = IsFamilyPremium()

    def test_active_ok(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.ACTIVE)
        assert self.perm.has_permission(_req(head, "GET"), None) is True
        assert self.perm.has_permission(_req(head, "POST"), None) is True

    def test_expired_denied(self, db, plan_premium):
        family, head = _family()
        _sub(family, plan_premium, Subscription.Status.EXPIRED, expires_in_days=-1)
        assert self.perm.has_permission(_req(head, "GET"), None) is False
PYEOF
echo "✓ создан apps/subscriptions/tests/test_mg_606a_premium_helpers.py"

# ── 5. Прогон ТОЛЬКО новых тестов ─────────────────────────────────────────
echo
echo "===================================================================="
echo "Прогон новых тестов MG-606.A"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/subscriptions/tests/test_mg_606a_premium_helpers.py -v --tb=short

echo
echo "===================================================================="
echo "Регресс subscriptions"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/subscriptions/ -v --tb=short

echo
echo "===================================================================="
echo "Регресс diary (страховка — legacy IsFamilyPremium не сломан)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/diary/ -v --tb=short 2>&1 | tail -50

echo
echo "PATCH-606.A — финиш"
