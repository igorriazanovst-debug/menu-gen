"""Общая логика слияния продуктов (используется dedup_products и dedup_products_ai).

merge_product_into перепривязывает все ссылки на канон, переносит КБЖУ при
нехватке, записывает имя дубля синонимом и удаляет дубль. Вызывать внутри
transaction.atomic().
"""


def has_kbju(p):
    return isinstance(p.nutrition, dict) and len(p.nutrition) > 0


def merge_product_into(dup, canon):
    """Слить продукт dup в canon. Возвращает счётчики перенесённых ссылок."""
    from apps.recipes.models import RecipeProduct
    from apps.shopping.models import ShoppingListItem

    from .aliases import learn_alias
    from .models import FridgeItem, Product, ProductAlias

    stats = {"fridge": 0, "recipe": 0, "shop": 0, "kbju": 0}
    stats["fridge"] = FridgeItem.objects.filter(product_id=dup.id).update(product_id=canon.id)
    stats["recipe"] = RecipeProduct.objects.filter(product_id=dup.id).update(product_id=canon.id)
    stats["shop"] = ShoppingListItem.objects.filter(product_id=dup.id).update(product_id=canon.id)

    # алиасы дубля -> канон (с учётом unique alias_norm)
    for a in ProductAlias.objects.filter(product_id=dup.id):
        if ProductAlias.objects.filter(alias_norm=a.alias_norm).exclude(id=a.id).exists():
            a.delete()
        else:
            a.product_id = canon.id
            a.save(update_fields=["product"])

    # перенос КБЖУ в канон, если у него пусто, а у дубля есть
    if not has_kbju(canon) and has_kbju(dup):
        canon.nutrition = dup.nutrition
        canon.calories_per_100g = dup.calories_per_100g
        canon.save(update_fields=["nutrition", "calories_per_100g"])
        stats["kbju"] = 1

    # имя дубля -> синоним канона (на будущее)
    learn_alias(dup.name, canon, source="merge")
    Product.objects.filter(id=dup.id).delete()
    return stats
