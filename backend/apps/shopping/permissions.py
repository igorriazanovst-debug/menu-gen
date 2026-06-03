# MG_SHOP001_permissions
from apps.family.models import Family, FamilyMember

from .models import ShoppingListAccess


def get_user_family(user):
    """Family where user is owner or member. None if absent."""
    fam = Family.objects.filter(owner=user).first()
    if fam:
        return fam
    fm = FamilyMember.objects.filter(user=user).select_related("family").first()
    return fm.family if fm else None


def is_family_head(user, family):
    return user.user_type == "admin" or family.owner_id == user.id


def access_level(user, shopping_list):
    """Return dict of capabilities for user on a list.
    Owner family head → full. Family member → read+toggle (own family).
    Explicit ShoppingListAccess → its flags. Else None (no access)."""
    fam = shopping_list.family
    if is_family_head(user, fam):
        return {"read": True, "toggle": True, "export": True, "manage": True}

    if FamilyMember.objects.filter(family=fam, user=user).exists():
        return {"read": True, "toggle": True, "export": True, "manage": False}

    acc = ShoppingListAccess.objects.filter(
        shopping_list=shopping_list, user=user
    ).first()
    if acc:
        return {
            "read": acc.can_read,
            "toggle": acc.can_toggle,
            "export": acc.can_export,
            "manage": False,
        }
    return None
