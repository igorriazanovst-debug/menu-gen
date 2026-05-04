"""
MG-205: пермишены для специалистов.

IsVerifiedSpecialist — текущий user является verified Specialist'ом.
SpecialistCanEditClientProfile — текущий user является verified Specialist'ом
    с активным SpecialistAssignment на семью target user.

is_verified_specialist_for_user(actor, target_user) — хелпер для
определения source='specialist' в serializers.
"""
from __future__ import annotations

from rest_framework import permissions

MG_205_V = 1


def _get_specialist(user):
    """Возвращает Specialist instance или None."""
    if not user or not user.is_authenticated:
        return None
    # related_name='specialist_profile' (см. apps/specialists/models.py)
    try:
        return user.specialist_profile
    except Exception:
        return None


def is_verified_specialist_for_user(actor, target_user) -> bool:
    """True, если actor — verified Specialist с активным assignment
    на любую из семей, в которой состоит target_user."""
    if not actor or not target_user:
        return False
    if actor.id == target_user.id:
        return False  # сам себе не специалист
    spec = _get_specialist(actor)
    if not spec or not spec.is_verified:
        return False

    # local imports чтобы избежать циклов
    from apps.family.models import FamilyMember
    from apps.specialists.models import SpecialistAssignment

    target_family_ids = list(
        FamilyMember.objects.filter(user=target_user).values_list("family_id", flat=True)
    )
    if not target_family_ids:
        return False

    return SpecialistAssignment.objects.filter(
        specialist=spec,
        family_id__in=target_family_ids,
        status=SpecialistAssignment.Status.ACTIVE,
    ).exists()


class IsVerifiedSpecialist(permissions.BasePermission):
    """Текущий user — verified Specialist."""

    def has_permission(self, request, view):
        spec = _get_specialist(request.user)
        return spec is not None and spec.is_verified


class SpecialistCanEditClientProfile(permissions.BasePermission):
    """Specialist может править профиль клиента из назначенной семьи.

    Ожидает, что view предоставит target_user через get_target_user(),
    или target_member через get_target_member().
    """

    def has_permission(self, request, view):
        spec = _get_specialist(request.user)
        if not spec or not spec.is_verified:
            return False
        target_user = None
        if hasattr(view, "get_target_user"):
            target_user = view.get_target_user()
        elif hasattr(view, "get_target_member"):
            m = view.get_target_member()
            target_user = getattr(m, "user", None) if m else None
        if target_user is None:
            return False
        return is_verified_specialist_for_user(request.user, target_user)
