"""MG_OWNDIARY: закрепить владельца — поле обязательное, день у человека один.

Написана руками, а не `makemigrations`: тот на превращении поля в обязательное
спрашивает про значение по умолчанию и ждёт ответа в терминале. Умолчание тут не
нужно — владелец уже проставлен в 0009, и если бы там осталась хоть одна строка
без него, 0009 упала бы сама, с объяснением.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("diary", "0009_own_diary_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="diaryentry",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="diary_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="waterlog",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="water_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="weightlog",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="weight_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="waterlog",
            unique_together={("user", "date")},
        ),
        migrations.AlterUniqueTogether(
            name="weightlog",
            unique_together={("user", "date")},
        ),
    ]
