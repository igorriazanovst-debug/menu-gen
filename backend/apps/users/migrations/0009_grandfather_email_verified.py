"""MG_EMAILVERIFY: помечаем всех существующих пользователей как подтверждённых,
чтобы строгий гейт логина не заблокировал уже зарегистрированные аккаунты.
Подтверждение требуется только для НОВЫХ e-mail-регистраций.
"""

from django.db import migrations


def grandfather(apps, schema_editor):
    User = apps.get_model("users", "User")
    from django.utils import timezone

    User.objects.filter(email_verified_at__isnull=True).update(email_verified_at=timezone.now())


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_user_email_verified_at"),
    ]

    operations = [
        migrations.RunPython(grandfather, noop),
    ]
