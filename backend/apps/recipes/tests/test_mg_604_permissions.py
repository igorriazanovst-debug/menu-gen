# MG_604_V_tests
"""
MG-604: unit-покрытие apps/recipes/permissions.py.

Missing lines:
  9   IsAuthorOrAdmin: SAFE_METHODS → True
  11  IsAuthorOrAdmin: user_type == 'admin' → True
  20  IsRecipeAuthorRole: SAFE_METHODS → True
"""

import pytest

from apps.recipes.permissions import IsAuthorOrAdmin, IsRecipeAuthorRole


class _Req:
    def __init__(self, method, user):
        self.method = method
        self.user = user


class _Obj:
    def __init__(self, author):
        self.author = author


@pytest.mark.django_db
class TestIsAuthorOrAdmin:
    def test_safe_method_returns_true(self, plain_user, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("GET", plain_user)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_admin_can_edit(self, admin, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", admin)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_author_can_edit(self, author, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", author)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_other_user_cannot_edit(self, plain_user, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", plain_user)
        assert perm.has_object_permission(req, None, recipe) is False


@pytest.mark.django_db
class TestIsRecipeAuthorRole:
    def test_safe_method_returns_true(self, plain_user):
        perm = IsRecipeAuthorRole()
        req = _Req("GET", plain_user)
        assert perm.has_permission(req, None) is True

    def test_recipe_author_can(self, author):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", author)
        assert perm.has_permission(req, None) is True

    def test_admin_can(self, admin):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", admin)
        assert perm.has_permission(req, None) is True

    def test_plain_user_cannot(self, plain_user):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", plain_user)
        assert perm.has_permission(req, None) is False
