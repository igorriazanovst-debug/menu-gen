# MG_T01_MAYO — merge duplicate «Майонез» Product into canonical (sauces) + seed alias.
from django.db import migrations


def forward(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    ProductAlias = apps.get_model("fridge", "ProductAlias")
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    FridgeItem = apps.get_model("fridge", "FridgeItem")
    RecipeProduct = apps.get_model("recipes", "RecipeProduct")
    ShoppingListItem = apps.get_model("shopping", "ShoppingListItem")

    from apps.fridge.aliases import normalize_alias

    NORM = "майонез"
    CANON_SLUG = "sauces"

    members = [p for p in Product.objects.all() if normalize_alias(p.name) == NORM]
    if len(members) < 2:
        # still ensure the alias exists for the lone canonical, if any
        if members:
            canon = members[0]
            ProductAlias.objects.update_or_create(
                alias_norm=NORM, defaults={"product_id": canon.id, "source": "manual"}
            )
        return

    # canonical = the one already in `sauces`, else lowest id
    canon = next((p for p in members if p.category_fk and getattr(p.category_fk, "slug", "") == CANON_SLUG), None)
    if canon is None:
        canon = min(members, key=lambda x: x.id)

    # force survivor category to sauces
    cat = ProductCategory.objects.filter(slug=CANON_SLUG).first()
    if cat is not None and canon.category_fk_id != cat.id:
        canon.category_fk = cat
        canon.save(update_fields=["category_fk"])

    for d in [p for p in members if p.id != canon.id]:
        FridgeItem.objects.filter(product_id=d.id).update(product_id=canon.id)
        ShoppingListItem.objects.filter(product_id=d.id).update(product_id=canon.id)
        RecipeProduct.objects.filter(product_id=d.id).update(product_id=canon.id, name_canonical=canon.name)
        ProductAlias.objects.filter(product_id=d.id).update(product_id=canon.id)
        d.delete()

    ProductAlias.objects.update_or_create(
        alias_norm=NORM, defaults={"product_id": canon.id, "source": "manual"}
    )


def backward(apps, schema_editor):
    # Non-destructive: keep merged data and alias.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0010_seed_aliases_feta_chicken"),
        ("recipes", "0015_recipeproduct"),
        ("shopping", "0005_shoppinglistaccess_status"),
    ]

    operations = [migrations.RunPython(forward, backward)]
