"""MG_NOBUY: признак «не класть в список покупок» и отметка воды.

Вода в рецептах есть почти везде, а в магазине её не покупают. В списке она
занимала строку и сбивала счёт: «Вода — 2.5 л» человек вычёркивал каждый раз
заново.

Признак ставится у товара, а не зашит списком имён в коде: что не покупается,
зависит от хозяйства. Миграция отмечает только воду и лёд — то, о чём говорили
прямо, — и только в общем каталоге. Продукты семей не трогаются: это чужие
записи, и решать за них нельзя.

Обратный ход снимает признак со всех записей: поле уходит целиком, и
восстанавливать ручные отметки всё равно неоткуда.
"""

from django.db import migrations, models

# Точные имена, а не «всё, где есть слово вода»: «Вода с газом» — покупают,
# «Вода розовая» (кондитерская) — тоже.
NOBUY = ["вода", "вода питьевая", "вода холодная", "вода горячая", "вода тёплая", "вода теплая", "лед", "лёд"]


def mark_water(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    for name in NOBUY:
        Product.objects.filter(owner_family__isnull=True, name__iexact=name).update(skip_in_shopping=True)


def unmark(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    Product.objects.filter(skip_in_shopping=True).update(skip_in_shopping=False)


class Migration(migrations.Migration):

    dependencies = [("fridge", "0024_nuts_category")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="skip_in_shopping",
            field=models.BooleanField(
                default=False, help_text="Не добавлять в список покупок (вода, лёд и прочее, что не покупают)."
            ),
        ),
        migrations.RunPython(mark_water, unmark),
    ]
