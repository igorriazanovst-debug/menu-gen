"""MG-605.C: права на конкретную запись дневника.

IsDiaryEntryOwner — кто может править и удалять запись.
Просмотр (SAFE_METHODS) уже ограничен через get_queryset.

MG_OWNDIARY: владелец — человек (`user`), а не его членство в семье. Раньше
сравнивали с `member`, и запись, сделанная тем же человеком за другим столом,
переставала быть его собственной: править её он не мог.

MG_HEADKEEPS: кроме владельца, править может глава семьи — но не всегда, а
только когда участник это разрешил или когда он несовершеннолетний. Правило
целиком живёт в access.py: оно про приватность, и второй его копии быть не
должно.
"""

from rest_framework import permissions

from apps.family.models import FamilyMember
from apps.family.selection import current_membership  # MG_ONEFAMILY

from .access import can_edit_of


class IsDiaryEntryOwner(permissions.BasePermission):
    """Изменять и удалять — владельцу, а также главе семьи по разрешению."""

    message = "Изменять можно только свои записи."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if obj.user_id == request.user.id:
            return True

        # MG_HEADKEEPS: свою же запись автор поправит и уберёт без разрешения.
        # Иначе ошибка главы («внёс обед не тому») оставалась бы в чужом
        # дневнике навсегда: убрать её мог бы только сам участник, который её и
        # не делал. Разрешение участника — про его собственные записи, а не про
        # чужие строки в его дне.
        if obj.added_by_id and obj.added_by_id == request.user.id:
            return True

        # Чужая запись, внесённая её владельцем. Смотрим, за каким столом она
        # сделана: глава отвечает за свою семью, а не за всю историю человека.
        current = current_membership(request.user)
        if current is None or obj.member_id is None:
            return False
        target = FamilyMember.objects.select_related("user__profile").filter(pk=obj.member_id).first()
        if target is None:
            return False
        allowed = can_edit_of(current, target)
        if not allowed:
            self.message = (
                "Участник не разрешил главе семьи править свои записи. " "Он может включить это у себя в профиле."
            )
        return allowed
