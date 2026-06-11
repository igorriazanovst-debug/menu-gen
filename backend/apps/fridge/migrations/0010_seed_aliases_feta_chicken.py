# MG_ALIASDEDUP — seed aliases: «Сыр Фета»→«Фета», «Филе куриное»/«Куриное филе»→«Курица (филе)».
from django.db import migrations


def forward(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    ProductAlias = apps.get_model("fridge", "ProductAlias")
    from apps.fridge.aliases import normalize_alias

    def find_by_norm(norm_target):
        for p in Product.objects.all():
            if normalize_alias(p.name) == norm_target:
                return p
        return None

    SEED = {
        "Фета": ["Сыр Фета"],
        "Курица (филе)": ["Филе куриное", "Куриное филе"],
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
            ProductAlias.objects.update_or_create(
                alias_norm=n, defaults={"product_id": prod.id, "source": "manual"}
            )


def backward(apps, schema_editor):
    # Non-destructive.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0009_merge_eggs_seed_aliases"),
    ]

    operations = [migrations.RunPython(forward, backward)]
