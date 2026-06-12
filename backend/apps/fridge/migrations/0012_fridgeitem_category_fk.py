# MG_T07 — per-item category override on FridgeItem.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0011_merge_mayo_seed_alias"),
    ]

    operations = [
        migrations.AddField(
            model_name="fridgeitem",
            name="category_fk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fridge_items",
                to="fridge.productcategory",
            ),
        ),
    ]
