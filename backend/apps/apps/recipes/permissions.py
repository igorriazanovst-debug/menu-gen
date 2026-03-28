from rest_framework import permissions


class IsAuthorOrAdmin(permissions.BasePermission):
    """Редактировать/удалять может только автор или admin."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.user_type == "admin":
            return True
        return obj.author == request.user


class IsRecipeAuthorRole(permissions.BasePermission):
    """Создавать рецепты могут только авторы или admin."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.user_type in ("recipe_author", "admin")
