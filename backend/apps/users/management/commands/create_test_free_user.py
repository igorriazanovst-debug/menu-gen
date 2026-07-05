"""Создаёт (или обновляет) тестового бесплатного пользователя для проверки freemium.

Free-пользователь — это обычный аккаунт с семьёй, но БЕЗ premium-подписки:
ему доступна генерация меню в пределах бесплатной квоты (см. apps.subscriptions.quota).

Пример:
    python manage.py create_test_free_user
    python manage.py create_test_free_user --email free@menugen.test --password '1234!' --name 'Free Тест'
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.family.models import Family, FamilyMember
from apps.users.models import Profile, User


class Command(BaseCommand):
    help = "Создаёт тестового бесплатного (Free) пользователя с семьёй, без premium."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="free@menugen.test")
        parser.add_argument("--password", default="1234!")
        parser.add_argument("--name", default="Free Тест")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        name = options["name"]

        user, created = User.objects.get_or_create(email=email, defaults={"name": name, "user_type": "user"})
        # set_password обходит валидаторы паролей (они срабатывают только в формах/
        # сериализаторах), поэтому простой пароль вроде "1234!" допустим для теста.
        user.name = name
        user.set_password(password)
        user.save()

        Profile.objects.get_or_create(user=user)

        family = Family.objects.filter(owner=user).first()
        if family is None:
            family = Family.objects.create(owner=user, name=f"Семья {name}")
        FamilyMember.objects.get_or_create(family=family, user=user, defaults={"role": FamilyMember.Role.HEAD})

        action = "создан" if created else "обновлён"
        self.stdout.write(
            self.style.SUCCESS(
                f"Free-пользователь {action}: {email} / {password} " f"(семья «{family.name}», без premium-подписки)."
            )
        )
