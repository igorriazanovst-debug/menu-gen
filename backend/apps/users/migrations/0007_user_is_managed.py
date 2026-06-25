# MG_MANAGEDMEMBER: family member without their own login.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_mg_skin_user_ui_skin"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_managed",
            field=models.BooleanField(default=False),
        ),
    ]
