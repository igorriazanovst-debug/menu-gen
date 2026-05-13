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
