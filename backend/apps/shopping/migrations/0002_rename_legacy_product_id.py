# MG_RUBRIC003 — rename attribute only at Django state level.
# DB column stays "product_id" (model field declares db_column="product_id"),
# so no data is touched; only the Python attribute name changes.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="shoppinglistitem",
                    name="product_id",
                ),
                migrations.AddField(
                    model_name="shoppinglistitem",
                    name="legacy_product_id",
                    field=models.BigIntegerField(
                        null=True, blank=True, db_column="product_id"
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
