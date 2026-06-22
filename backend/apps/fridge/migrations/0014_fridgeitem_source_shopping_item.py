# MG_SHOP2FRIDGE: link a fridge item to the shopping item it was bought from.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0013_product_source"),
        ("shopping", "0005_shoppinglistaccess_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="fridgeitem",
            name="source_shopping_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fridge_items",
                to="shopping.shoppinglistitem",
            ),
        ),
        migrations.AddIndex(
            model_name="fridgeitem",
            index=models.Index(
                fields=["source_shopping_item"],
                name="fridge_item_src_shop_idx",
            ),
        ),
    ]
