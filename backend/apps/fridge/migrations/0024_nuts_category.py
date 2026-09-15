"""MG_NUTSCAT: рубрика «Орехи и сухофрукты».

Простановка рубрик моделью (mg_fix_categories) на пробной сотне отправила в
«Сладости» девять записей подряд: «Орехи», «Миндаль», «Арахис», «Фисташки»,
«Фундук», «Грецкий орех», «Кедровые орешки», «Миндальные лепестки». Ошибкой
модели это назвать нельзя — подходящей рубрики в списке просто не было, и она
выбирала ближайшую. В каталоге при этом «Орех грецкий» лежал в «Специях и
приправах»: единого правила не существовало вовсе.

Решение согласовано: заводим отдельную рубрику. В магазине это отдельная полка,
и в списке покупок орехи с сухофруктами собираются вместе, а не расходятся между
шоколадом и солью.

Существующие записи миграция НЕ перекладывает. Переложить — работа
mg_fix_categories, и она идёт с dry-run: решать, что «Кокосовая стружка» это
орехи, а «Сироп от ананасов» нет, миграция не должна.

Место в списке — сразу после сладостей: сортировка 125 между sweets (120) и
condiments (130).
"""

from django.db import migrations

SLUG = "nuts"


def add(apps, schema_editor):
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    ProductCategory.objects.get_or_create(
        slug=SLUG,
        defaults={
            "name_ru": "Орехи и сухофрукты",
            "name_en": "Nuts and dried fruits",
            "icon": "🥜",
            "color": "#EFEBE9",
            "sort_order": 125,
            "is_active": True,
            # Год: орехи и сухофрукты в закрытой упаковке столько и лежат.
            "shelf_life_days": 365,
        },
    )


def remove(apps, schema_editor):
    """Откат: рубрику убираем, только если на неё никто не успел сослаться.

    Продукты ссылаются на категорию через SET_NULL/PROTECT в зависимости от
    поля, но дело не в этом: снести рубрику, по которой уже разложены записи,
    значит вернуть их в «Прочее» молча. Лучше оставить лишнюю строку в списке.
    """
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    Product = apps.get_model("fridge", "Product")
    cat = ProductCategory.objects.filter(slug=SLUG).first()
    if cat and not Product.objects.filter(category_fk_id=cat.id).exists():
        cat.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0023_alter_product_source"),
    ]

    operations = [
        migrations.RunPython(add, remove),
    ]
