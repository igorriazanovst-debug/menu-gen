"""MG-605.C: Premium gate.

Хелпер `has_active_premium(family)` и DRF-permission `IsFamilyPremium`.

Premium = у семьи есть подписка с:
- plan.code == 'premium'
- status IN ('active', 'trial')
- expires_at > now()
"""
from django.utils import timezone
from rest_framework import permissions

from apps.family.models import FamilyMember
from .models import Subscription


PREMIUM_PLAN_CODE = "premium"
PREMIUM_ACTIVE_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.TRIAL)


def has_active_premium(family) -> bool:
    """Возвращает True, если у семьи есть активная Premium-подписка."""
    if family is None:
        return False
    return Subscription.objects.filter(
        family=family,
        plan__code=PREMIUM_PLAN_CODE,
        status__in=PREMIUM_ACTIVE_STATUSES,
        expires_at__gt=timezone.now(),
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
    """Разрешает доступ только если у семьи пользователя активна Premium."""

    message = "Требуется активная Premium-подписка."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        family = get_user_family(request.user)
        return has_active_premium(family)
