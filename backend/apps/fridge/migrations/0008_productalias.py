# MG_PRODALIAS
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("fridge", "0007_product_last_price_product_last_price_at")]

    operations = [
        migrations.CreateModel(
            name="ProductAlias",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alias_norm", models.CharField(max_length=255, unique=True)),
                ("source", models.CharField(default="manual", help_text="manual|auto", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aliases",
                        to="fridge.product",
                    ),
                ),
            ],
            options={"db_table": "product_aliases"},
        ),
    ]
