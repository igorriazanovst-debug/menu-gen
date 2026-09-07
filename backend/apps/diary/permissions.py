"""MG-605.C: права на конкретную запись дневника.

IsDiaryEntryOwner — редактировать/удалять может только владелец записи.
Просмотр (SAFE_METHODS) уже ограничен через get_queryset.

MG_OWNDIARY: владелец — человек (`user`), а не его членство в семье. Раньше
сравнивали с `member`, и запись, сделанная тем же человеком за другим столом,
переставала быть его собственной: править её он не мог.
"""

from rest_framework import permissions


class IsDiaryEntryOwner(permissions.BasePermission):
    """Изменять/удалять может только владелец записи."""

    message = "Изменять можно только свои записи."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id
