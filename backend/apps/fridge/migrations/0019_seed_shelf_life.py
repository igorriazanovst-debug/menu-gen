"""MG_SHELFLIFE: стартовые сроки хранения по категориям.

Числа — «сколько живёт ПОСЛЕ ПОКУПКИ», а не срок с этикетки: производство нам
неизвестно, и поправка на пролежавшее уже учтена. Значения намеренно
консервативные — лучше напомнить на день раньше, чем предложить съесть
испортившееся.

Заполняем только пустые: правки в админке миграция не перетирает. Категории,
которых нет в списке (бытовая химия, гигиена, корм, «прочее»), остаются пустыми —
это значит «не подставлять срок», и для не-еды так и надо.
"""

from django.db import migrations

SHELF_LIFE = {
    "bakery": 3,  # хлеб черствеет быстро
    "canned": 365,
    "cheese": 14,
    "condiments": 365,
    "dairy": 5,
    "drinks": 30,
    "eggs": 21,
    "fish": 2,  # самое скоропортящееся
    "frozen": 90,
    "fruits": 7,
    "grains": 180,
    "meat": 3,
    "oils": 120,
    "ready": 2,  # готовая еда
    "sauces": 60,
    "sausages": 7,
    "sweets": 60,
    "vegetables": 10,
}


def seed(apps, schema_editor):
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    filled = 0
    for slug, days in SHELF_LIFE.items():
        filled += ProductCategory.objects.filter(slug=slug, shelf_life_days__isnull=True).update(
            shelf_life_days=days
        )
    if filled:
        print(f"  MG_SHELFLIFE: сроки проставлены категориям: {filled}")


def unseed(apps, schema_editor):
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    ProductCategory.objects.filter(slug__in=list(SHELF_LIFE)).update(shelf_life_days=None)


class Migration(migrations.Migration):
    dependencies = [("fridge", "0018_product_shelf_life_days_and_more")]

    operations = [migrations.RunPython(seed, unseed)]
