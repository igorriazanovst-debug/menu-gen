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

MG_MERGEKEEP: и перенести нужно не только ссылки. Из полей самого продукта
слияние забирало одно — КБЖУ, — а остальное уходило вместе с удалённым дублём:
рубрика, признак курируемой записи, картинка, единица, срок хранения. Пока
выжившим всегда была самая «богатая» запись, это почти не проявлялось. Теперь
выживший выбирается по имени (MG_DEDUPSURVIVOR), и в план честно встают
«Моцарелла» (#68) -> «Сыр моцарелла» (#601), «Кальмары» (#86) -> «Кальмар»
(#1975): имя у выжившего правильное, а рубрики и КБЖУ у него может не быть.
Без переноса полей слияние сделало бы каталог беднее — и стёрло бы ровно те
рубрики, которые мы разложили отдельным прогоном.
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


# Поля, которые дубль отдаёт канону, если у канона пусто. Смысл тот же, что у
# переноса КБЖУ: слияние не должно делать запись беднее ни в чём.
_ABSORB_IF_EMPTY = (
    "category",  # старая текстовая рубрика, ещё читается импортом OFF
    "default_unit",
    "image_url",
    "subcategory",
    "popularity",
    "shelf_life_days",
)


def _is_empty(value):
    return value is None or value == ""


def _no_rubric(category):
    """«Прочее» — не рубрика, а её отсутствие (то же правило, что в списке покупок)."""
    return category is None or category.slug == "other"


def absorb_fields(canon, dup):
    """Дозаполнить пустые поля канона значениями дубля. Возвращает имена полей."""
    changed = []
    for field in _ABSORB_IF_EMPTY:
        if _is_empty(getattr(canon, field)) and not _is_empty(getattr(dup, field)):
            setattr(canon, field, getattr(dup, field))
            changed.append(field)

    if _no_rubric(canon.category_fk) and not _no_rubric(dup.category_fk):
        canon.category_fk = dup.category_fk
        changed.append("category_fk")

    # Курируемую запись слияние не должно разжаловать: is_seed защищает её от
    # mg_prune_auto_products, а source=auto — как раз то, что тот выпалывает.
    if dup.is_seed and not canon.is_seed:
        canon.is_seed = True
        changed.append("is_seed")
    if canon.source == "auto" and dup.source != "auto":
        canon.source = dup.source
        changed.append("source")

    # Цена и её дата — пара: врозь они врут.
    if canon.last_price is None and dup.last_price is not None:
        canon.last_price = dup.last_price
        canon.last_price_at = dup.last_price_at
        changed.extend(["last_price", "last_price_at"])

    if changed:
        canon.save(update_fields=changed)
    return changed


def merge_product_into(dup, canon):
    """Слить продукт dup в canon. Возвращает счётчики перенесённых ссылок."""
    from .aliases import learn_alias
    from .models import Product, ProductAlias

    stats = {"fridge": 0, "recipe": 0, "shop": 0, "kbju": 0, "fields": 0}
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

    stats["fields"] = len(absorb_fields(canon, dup))

    # имя дубля -> синоним канона (на будущее)
    learn_alias(dup.name, canon, source="merge")
    barcode = dup.barcode
    Product.objects.filter(id=dup.id).delete()

    # Штрих-код уникален на всю таблицу, поэтому он переезжает последним: пока
    # дубль жив, присвоение канону упало бы на ограничении.
    if barcode and not canon.barcode:
        canon.barcode = barcode
        canon.save(update_fields=["barcode"])
        stats["fields"] += 1
    return stats
