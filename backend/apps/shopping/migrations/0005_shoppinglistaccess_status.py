# MG_SHAREACCEPT
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0004_purchasehistoryentry_price_per_unit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoppinglistaccess",
            name="status",
            field=models.CharField(
                default="accepted",
                max_length=10,
                choices=[
                    ("pending", "Ожидает принятия"),
                    ("accepted", "Принят"),
                    ("rejected", "Отклонён"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="shoppinglistaccess",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
