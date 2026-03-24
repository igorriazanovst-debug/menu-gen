from rest_framework import permissions


class IsFamilyHead(permissions.BasePermission):
    """Только глава семьи или admin."""

    def has_permission(self, request, view):
        if request.user.user_type == "admin":
            return True
        family = view.get_family()
        return family.owner_id == request.user.id
