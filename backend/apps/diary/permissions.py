"""MG-605.C: права на конкретную запись дневника.

IsDiaryEntryOwner — редактировать/удалять может только владелец записи
(member которой = FamilyMember текущего user-а).
Просмотр (SAFE_METHODS) уже ограничен через get_queryset.
"""

from rest_framework import permissions

from apps.family.models import FamilyMember


class IsDiaryEntryOwner(permissions.BasePermission):
    """Изменять/удалять может только владелец записи."""

    message = "Изменять можно только свои записи."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Владелец = FamilyMember текущего юзера == obj.member
        return FamilyMember.objects.filter(user=request.user, pk=obj.member_id).exists()
