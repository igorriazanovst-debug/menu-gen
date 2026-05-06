# MG_304_V_migration
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0006_component_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="menu",
            name="warnings",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
