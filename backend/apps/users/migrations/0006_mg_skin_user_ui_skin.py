# MG_SKIN: поле выбранного скина оформления у пользователя.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_mg_504_profile_cheat_meal"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="ui_skin",
            field=models.CharField(
                choices=[("main", "Основная"), ("second", "Альтернативная")],
                default="main",
                max_length=16,
            ),
        ),
    ]
