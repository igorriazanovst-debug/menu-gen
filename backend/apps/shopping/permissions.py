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
        return {"read": True, "toggle": True, "export": True, "manage": True, "pending": False}

    if FamilyMember.objects.filter(family=fam, user=user).exists():
        return {"read": True, "toggle": True, "export": True, "manage": False, "pending": False}

    acc = ShoppingListAccess.objects.filter(shopping_list=shopping_list, user=user).first()
    if acc:
        # MG_SHAREACCEPT: rejected -> no access; pending -> read-only preview
        # (recipient can view the contents before accepting/rejecting, but the
        # list does not appear in the main listing and cannot be modified).
        if acc.status == ShoppingListAccess.Status.REJECTED:
            return None
        if acc.status == ShoppingListAccess.Status.PENDING:
            return {"read": True, "toggle": False, "export": False, "manage": False, "pending": True}
        return {
            "read": acc.can_read,
            "toggle": acc.can_toggle,
            "export": acc.can_export,
            "manage": False,
            "pending": False,
        }
    return None
