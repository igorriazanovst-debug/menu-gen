"""MG_DEVMIRROR: обезличивание копии прода на dev.

Главная проверка здесь — не то, что команда стирает данные, а то, что она
ОТКАЗЫВАЕТСЯ это делать где угодно, кроме dev. Команда живёт в том же репозитории,
что и прод; одна невнимательная строка в консоли боевого сервера — и настоящие
адреса заменены на dev.local без возможности вернуть.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.family.models import Family
from apps.payments.models import Payment
from apps.social.models import SocialLink
from apps.users.models import PhoneVerification, User


@pytest.fixture
def people(db):
    user = User.objects.create_user(email="real@example.com", name="Иван Петров", password="pass12345")
    user.phone = "+79990000001"
    user.avatar_url = "https://example.com/ava.jpg"
    user.save()
    staff = User.objects.create_user(
        email="admin@example.com", name="Админ", password="pass12345", is_staff=True
    )
    return user, staff


def run(**kwargs):
    call_command("sanitize_dev", **kwargs)


@pytest.mark.django_db
class TestGuard:
    def test_на_проде_отказывается(self, people, settings):
        settings.MENUGEN_ENV = "prod"

        with pytest.raises(CommandError, match="только на dev"):
            run(yes=True)

        assert User.objects.filter(email="real@example.com").exists()

    def test_без_пометки_контура_считается_продом(self, people, settings):
        """Значение по умолчанию — prod: забытая переменная не стоит данных."""
        del settings.MENUGEN_ENV

        with pytest.raises(CommandError):
            run(yes=True)

        assert User.objects.filter(email="real@example.com").exists()

    def test_без_подтверждения_не_запускается(self, people, settings):
        settings.MENUGEN_ENV = "dev"

        with pytest.raises(CommandError, match="--yes"):
            run()

        assert User.objects.filter(email="real@example.com").exists()


@pytest.mark.django_db
class TestSanitize:
    def test_обычный_пользователь_обезличен(self, people, settings):
        settings.MENUGEN_ENV = "dev"
        user, _ = people

        run(yes=True)

        user.refresh_from_db()
        assert user.email == f"user{user.id}@dev.local"
        assert user.name == f"Пользователь {user.id}"
        assert user.phone is None
        assert user.avatar_url is None
        assert not user.has_usable_password()

    def test_сотрудник_не_тронут(self, people, settings):
        """Под сотрудником заходят в админку dev — иначе контур бесполезен."""
        settings.MENUGEN_ENV = "dev"
        _, staff = people

        run(yes=True)

        staff.refresh_from_db()
        assert staff.email == "admin@example.com"
        assert staff.name == "Админ"
        assert staff.check_password("pass12345")

    def test_адрес_из_списка_исключений_остаётся(self, people, settings):
        settings.MENUGEN_ENV = "dev"
        user, _ = people

        run(yes=True, keep_emails="real@example.com")

        user.refresh_from_db()
        assert user.email == "real@example.com"

    def test_привязки_к_мессенджерам_удалены(self, people, settings):
        """Иначе бот с dev напишет живому человеку."""
        settings.MENUGEN_ENV = "dev"
        PhoneVerification.objects.create(
            phone="+79990000001",
            token="tok-1",
            chat_id="123456",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        run(yes=True)

        assert not PhoneVerification.objects.exists()

    def test_токен_соцсети_стёрт(self, people, settings):
        settings.MENUGEN_ENV = "dev"
        user, _ = people
        link = SocialLink.objects.create(
            user=user, provider=SocialLink.Provider.VK, provider_user_id="42", access_token="секрет"
        )

        run(yes=True)

        link.refresh_from_db()
        assert link.access_token == ""
        assert link.is_active is False

    def test_платёж_отвязан_от_провайдера(self, people, settings):
        """С dev нельзя дотянуться до настоящего платежа в ЮKassa."""
        settings.MENUGEN_ENV = "dev"
        user, _ = people
        family = Family.objects.create(owner=user, name="Семья")
        pay = Payment.objects.create(
            family=family, amount=Decimal("500.00"), status=Payment.Status.SUCCEEDED, payment_id="real-yk-id"
        )

        run(yes=True)

        pay.refresh_from_db()
        assert pay.payment_id is None
        assert pay.amount == Decimal("500.00"), "сумма нужна для проверки истории платежей"

    def test_периодические_задачи_выключены(self, people, settings):
        """Рассылки с копии прода ушли бы настоящим адресатам."""
        settings.MENUGEN_ENV = "dev"
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        sched, _ = CrontabSchedule.objects.get_or_create(minute="0", hour="9")
        task = PeriodicTask.objects.create(
            name="check-fridge-expiry", task="apps.notifications.tasks.check_fridge_expiry", crontab=sched
        )

        run(yes=True)

        task.refresh_from_db()
        assert task.enabled is False

    def test_повторный_запуск_безопасен(self, people, settings):
        settings.MENUGEN_ENV = "dev"
        user, _ = people

        run(yes=True)
        run(yes=True)

        user.refresh_from_db()
        assert user.email == f"user{user.id}@dev.local"
