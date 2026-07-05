"""MG_STRAT_PLATE — macro-role classifier (ProductCategory.slug -> macro roles).

Roles are derived ONLY from the product category (presence logic):
a recipe "has" a role if >=1 of its linked ingredients belongs to a category
mapping to that role. Source of truth = this module (Python constant).
Per-product overrides and admin editing -> BACKLOG.
"""

from __future__ import annotations

# Macro roles
PROTEIN = "protein"
FAT = "fat"
CARB_COMPLEX = "carb_complex"
CARB_SIMPLE = "carb_simple"
FIBER = "fiber"

CARB_ANY = frozenset({CARB_COMPLEX, CARB_SIMPLE})

# category slug -> set of roles (confirmed mapping, chat strategy)
MACRO_ROLES = {
    "meat": frozenset({PROTEIN}),
    "fish": frozenset({PROTEIN}),
    "eggs": frozenset({PROTEIN}),
    "cheese": frozenset({PROTEIN, FAT}),
    "sausages": frozenset({PROTEIN, FAT}),
    "dairy": frozenset({PROTEIN, FAT}),
    "grains": frozenset({CARB_COMPLEX}),
    "bakery": frozenset({CARB_COMPLEX}),
    "sweets": frozenset({CARB_SIMPLE}),
    "oils": frozenset({FAT}),
    "vegetables": frozenset({FIBER}),
    "fruits": frozenset({FIBER}),
    # no role (cannot be split by category alone / non-food):
    "canned": frozenset(),
    "frozen": frozenset(),
    "ready": frozenset(),
    "sauces": frozenset(),
    "condiments": frozenset(),
    "drinks": frozenset(),
    "other": frozenset(),
    "household": frozenset(),
    "hygiene": frozenset(),
    "pets": frozenset(),
}


def category_roles(slug: str) -> frozenset:
    """Roles for a category slug (empty frozenset if unknown/no-role)."""
    return MACRO_ROLES.get(slug or "", frozenset())


def recipe_roles(recipe) -> set:
    """Presence roles of a recipe from its linked ingredients.

    Iterates recipe.product_links; skips unlinked ingredients and products
    without a category. Cheap to prefetch with
    .prefetch_related('product_links__product__category_fk').
    """
    roles: set = set()
    for link in recipe.product_links.all():
        prod = link.product
        if prod is None:
            continue
        cat = prod.category_fk
        if cat is None:
            continue
        roles |= MACRO_ROLES.get(cat.slug, frozenset())
    return roles


def recipe_has_role(recipe, role: str) -> bool:
    return role in recipe_roles(recipe)


def recipe_has_carb(recipe) -> bool:
    """True if recipe carries any carbohydrate role (complex or simple)."""
    return bool(recipe_roles(recipe) & CARB_ANY)
