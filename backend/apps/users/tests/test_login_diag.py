"""MG_LOGINFIX: аккаунты, заведённые вручную, должны уметь входить.

Строгий гейт (EMAIL_VERIFICATION_REQUIRED) пускает только с подтверждённым
e-mail, а подтверждение приходит письмом при регистрации. Пользователь,
созданный в админке или через createsuperuser, письма не получал никогда — и
без этих правок не вошёл бы вообще никогда, сколько бы правильный пароль ни
вводил. Плюс команда диагностики: почему конкретный аккаунт получает отказ.
"""

from io import StringIO

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.urls import reverse

from apps.users.admin import AdminUserCreationForm, UserAdmin
from apps.users.management.commands.check_login import login_blockers
from apps.users.models import User


def make_admin_user(**overrides):
    """Создаёт пользователя ровно тем же путём, что и форма админки."""
    data = {
        "email": "manual@example.ru",
        "name": "Заведён вручную",
        "password1": "Sup3r-Passw0rd",
        "password2": "Sup3r-Passw0rd",
        "user_type": "user",
        "is_active": True,
    }
    data.update(overrides)
    form = AdminUserCreationForm(data=data)
    assert form.is_valid(), form.errors
    user = form.save()
    UserAdmin(User, AdminSite()).save_model(request=None, obj=user, form=form, change=False)
    return user


@pytest.mark.django_db
class TestManuallyCreatedAccounts:
    def test_admin_created_user_can_log_in_with_gate_on(self, client, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = True
        user = make_admin_user()

        assert user.is_email_verified

        r = client.post(
            reverse("auth-login"),
            {"email": "manual@example.ru", "password": "Sup3r-Passw0rd"},
            format="json",
        )
        assert r.status_code == 200, r.data
        assert "access" in r.data

    def test_superuser_from_cli_is_verified(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = True
        user = User.objects.create_superuser(email="root@example.ru", password="Sup3r-Passw0rd", name="root")

        assert user.is_email_verified
        assert login_blockers(user) == []

    def test_existing_user_is_not_touched_on_edit(self, settings):
        """Правка существующего пользователя не должна «подтверждать» его e-mail."""
        settings.EMAIL_VERIFICATION_REQUIRED = True
        user = User.objects.create_user(email="old@example.ru", password="x", name="Старый")
        user.email_verified_at = None
        user.save(update_fields=["email_verified_at"])

        UserAdmin(User, AdminSite()).save_model(request=None, obj=user, form=None, change=True)

        user.refresh_from_db()
        assert not user.is_email_verified


@pytest.mark.django_db
class TestLoginBlockers:
    def test_verified_active_user_has_no_blockers(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = True
        user = User.objects.create_user(email="ok@example.ru", password="x", name="ok")
        user.email_verified_at = "2026-01-01T00:00:00Z"
        user.save(update_fields=["email_verified_at"])

        assert login_blockers(user) == []

    def test_unverified_is_blocked_only_while_gate_is_on(self, settings):
        user = User.objects.create_user(email="new@example.ru", password="x", name="new")
        user.email_verified_at = None
        user.save(update_fields=["email_verified_at"])

        settings.EMAIL_VERIFICATION_REQUIRED = True
        assert any("не подтверждён" in r for r in login_blockers(user))

        settings.EMAIL_VERIFICATION_REQUIRED = False
        assert login_blockers(user) == []

    def test_inactive_and_passwordless_are_reported(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = False
        user = User.objects.create_user(email="off@example.ru", password=None, name="off")
        user.is_active = False
        user.save(update_fields=["is_active"])

        reasons = " ".join(login_blockers(user))
        assert "отключён" in reasons
        assert "пароль не задан" in reasons


@pytest.mark.django_db
class TestCheckLoginCommand:
    def _run(self, *args):
        out = StringIO()
        call_command("check_login", *args, stdout=out)
        return out.getvalue()

    def test_reports_missing_user(self):
        assert "нет в этой базе" in self._run("nobody@example.ru")

    def test_reports_gate_block_and_unblocks_with_flag(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = True
        user = User.objects.create_user(email="blocked@example.ru", password="x", name="b")
        user.email_verified_at = None
        user.save(update_fields=["email_verified_at"])

        assert "не подтверждён" in self._run("blocked@example.ru")

        self._run("blocked@example.ru", "--verify")
        user.refresh_from_db()
        assert user.is_email_verified

    def test_finds_user_by_phone(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = False
        User.objects.create_user(phone="+79000000001", password="x", name="ph")

        assert "вход разрешён" in self._run("+79000000001")

    def test_lists_everyone_the_gate_blocks(self, settings):
        settings.EMAIL_VERIFICATION_REQUIRED = True
        for i in range(3):
            u = User.objects.create_user(email=f"u{i}@example.ru", password="x", name=f"u{i}")
            u.email_verified_at = None
            u.save(update_fields=["email_verified_at"])

        out = self._run("--all-unverified")
        assert "Аккаунтов с неподтверждённым e-mail: 3" in out
        assert "u1@example.ru" in out
