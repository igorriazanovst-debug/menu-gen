"""Общая логика слияния продуктов (используется dedup_products и dedup_products_ai).

merge_product_into перепривязывает все ссылки на канон, переносит КБЖУ при
нехватке, записывает имя дубля синонимом и удаляет дубль. Вызывать внутри
transaction.atomic().

MG_MERGEALL: перепривязать нужно ВСЕ ссылки, а не те, что были во времена
написания команды. Дубль в конце удаляется, и ссылка, о которой здесь не
вспомнили, уйдёт вместе с ним: у menu.MenuItem и menu.ConstructedMealItem
(MG_PRODDISH, продукт как блюдо приёма) стоит CASCADE — из меню молча пропала
бы позиция. Поэтому список ниже строится из _meta, а не руками; новая ссылка
на продукт учтётся сама.
"""


def has_kbju(p):
    return isinstance(p.nutrition, dict) and len(p.nutrition) > 0


# Имена счётчиков, по которым отчитываются команды дедупа. Остальные ссылки
# считаются под меткой вида «menu.MenuItem» — их немного, и в отчёте видно, что
# именно переехало.
_STAT_NAME = {
    "fridge.FridgeItem": "fridge",
    "recipes.RecipeProduct": "recipe",
    "shopping.ShoppingListItem": "shop",
}


def merge_product_into(dup, canon):
    """Слить продукт dup в canon. Возвращает счётчики перенесённых ссылок."""
    from .aliases import learn_alias
    from .models import Product, ProductAlias

    stats = {"fridge": 0, "recipe": 0, "shop": 0, "kbju": 0}
    for rel in Product._meta.related_objects:
        model = rel.related_model
        if model is ProductAlias:
            continue  # у синонимов своё правило: см. ниже, unique alias_norm
        if rel.many_to_many:
            continue  # у связи через таблицу нет поля для update(); таких сейчас нет
        label = "%s.%s" % (model._meta.app_label, model.__name__)
        field = rel.field.name
        moved = model.objects.filter(**{"%s_id" % field: dup.id}).update(**{"%s_id" % field: canon.id})
        key = _STAT_NAME.get(label, label)
        stats[key] = stats.get(key, 0) + moved

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
