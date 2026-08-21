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


def specialist_shopping_families(user, write=False):
    """MG_COOK: семьи клиентов, чьи списки покупок открыты этому специалисту.

    Закупку матрица отдаёт повару, но весь модуль списков был написан до того,
    как повара появились: доступ там опирался на членство в семье или явную
    расшаренную ссылку. Специалист не подходил ни под одно — и роль, которой
    закупка поручена, не могла открыть ни один список.
    """
    from apps.specialists.access import Section, allows
    from apps.specialists.models import SpecialistAssignment

    spec = getattr(user, "specialist_profile", None) if user and user.is_authenticated else None
    if spec is None or not spec.is_verified:
        return []
    out = []
    for a in SpecialistAssignment.objects.filter(
        specialist=spec, status=SpecialistAssignment.Status.ACTIVE
    ).select_related("specialist"):
        if allows(a, Section.SHOPPING, write=write):
            out.append(a.family_id)
    return out


def resolve_write_family(user, family_id=None):
    """Семья, для которой пользователь вправе завести список покупок.

    Своя — если он глава семьи; клиентская — если роль даёт закупку. Явный
    family_id нужен специалисту: своей семьи у него в этом разговоре нет.
    """
    if family_id:
        allowed = specialist_shopping_families(user, write=True)
        if int(family_id) in allowed:
            return Family.objects.filter(id=family_id).first(), None
        # Свою семью тоже можно указать явно — но только главе.
        own = get_user_family(user)
        if own and str(own.id) == str(family_id) and is_family_head(user, own):
            return own, None
        return None, "Нет прав заводить список для этой семьи."

    own = get_user_family(user)
    if own:
        if not is_family_head(user, own):
            return None, "Только глава семьи."
        return own, None

    allowed = specialist_shopping_families(user, write=True)
    if len(allowed) == 1:
        return Family.objects.filter(id=allowed[0]).first(), None
    if allowed:
        return None, "Укажите семью клиента (family_id)."
    return None, "Нет семьи."


def access_level(user, shopping_list):
    """Return dict of capabilities for user on a list.
    Owner family head → full. Family member → read+toggle (own family).
    Специалист с правом закупки → полный доступ к спискам своего клиента.
    Explicit ShoppingListAccess → its flags. Else None (no access)."""
    fam = shopping_list.family
    if is_family_head(user, fam):
        return {"read": True, "toggle": True, "export": True, "manage": True, "pending": False}

    if FamilyMember.objects.filter(family=fam, user=user).exists():
        return {"read": True, "toggle": True, "export": True, "manage": False, "pending": False}

    # MG_COOK: повар ведёт закупку целиком, значит и правит список целиком.
    if fam.id in specialist_shopping_families(user, write=True):
        return {"read": True, "toggle": True, "export": True, "manage": True, "pending": False}

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
