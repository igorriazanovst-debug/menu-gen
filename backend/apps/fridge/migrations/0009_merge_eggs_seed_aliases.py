# MG_PRODALIAS — merge duplicate egg Product into canonical + seed aliases.
from django.db import migrations


def forward(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    ProductAlias = apps.get_model("fridge", "ProductAlias")
    RecipeProduct = apps.get_model("recipes", "RecipeProduct")
    FridgeItem = apps.get_model("fridge", "FridgeItem")
    ShoppingListItem = apps.get_model("shopping", "ShoppingListItem")

    from apps.fridge.aliases import normalize_alias

    def find_by_norm(norm_target):
        for p in Product.objects.all():
            if normalize_alias(p.name) == norm_target:
                return p
        return None

    # --- merge: any Product normalizing to "яйца куриные" but != canonical id ---
    canon = Product.objects.filter(name="Яйца куриные").first() or find_by_norm("яйца куриные")
    if canon is not None:
        dups = [p for p in Product.objects.all() if p.id != canon.id and normalize_alias(p.name) == "яйца куриные"]
        for d in dups:
            dup_link_ids = list(RecipeProduct.objects.filter(product_id=d.id).values_list("id", flat=True))
            RecipeProduct.objects.filter(id__in=dup_link_ids).update(product_id=canon.id, name_canonical=canon.name)
            FridgeItem.objects.filter(product_id=d.id).update(product_id=canon.id)
            ShoppingListItem.objects.filter(product_id=d.id).update(product_id=canon.id)
            ProductAlias.objects.filter(product_id=d.id).update(product_id=canon.id)
            d.delete()

    # --- seed aliases (idempotent) ---
    SEED = {
        "Яйца куриные": [
            "Яйцо",
            "Яйца",
            "Яйцо куриное",
            "Яйцо куриное С1",
            "Яйца С1",
            "Яйцо С1",
            "Яйца куриные C1",
            "яица",
            "яиц",
        ],
        "Помидоры": ["томат", "томаты", "помидор"],
    }
    for prod_name, variants in SEED.items():
        prod = Product.objects.filter(name=prod_name).first() or find_by_norm(normalize_alias(prod_name))
        if prod is None:
            continue
        prod_norm = normalize_alias(prod.name)
        for v in variants:
            n = normalize_alias(v)
            if not n or n == prod_norm:
                continue
            ProductAlias.objects.update_or_create(alias_norm=n, defaults={"product_id": prod.id, "source": "manual"})


def backward(apps, schema_editor):
    # Non-destructive: keep merged data and aliases.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0008_productalias"),
        ("recipes", "0015_recipeproduct"),
        ("shopping", "0005_shoppinglistaccess_status"),
    ]

    operations = [migrations.RunPython(forward, backward)]
