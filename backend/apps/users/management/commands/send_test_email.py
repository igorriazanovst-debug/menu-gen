"""Проверка SMTP-настроек: отправляет тестовое письмо на указанный адрес.

Пример:  python manage.py send_test_email you@example.com
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Отправляет тестовое письмо для проверки SMTP (EMAIL_* в .env)."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Адрес получателя тестового письма")

    def handle(self, *args, **opts):
        from apps.common.mail import email_enabled

        to = opts["to"]
        host = getattr(settings, "EMAIL_HOST", "") or ""
        sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
        # MG_MAILAPI: при HTTP API (Anymail) EMAIL_HOST пуст и не требуется —
        # проверяем настроенность по бэкенду, а не по наличию SMTP-хоста.
        if not email_enabled():
            raise CommandError("Отправка почты не настроена: для SMTP задайте EMAIL_HOST (см. .env).")

        self.stdout.write(f"Backend: {settings.EMAIL_BACKEND}")
        if host:
            proxy = getattr(settings, "EMAIL_PROXY", "") or ""
            self.stdout.write(
                f"SMTP {host}:{settings.EMAIL_PORT} "
                f"(TLS={settings.EMAIL_USE_TLS}, SSL={settings.EMAIL_USE_SSL}); прокси: "
                f"{proxy or 'нет (напрямую)'}"
            )
        self.stdout.write(f"От {sender} → {to}")
        try:
            sent = send_mail(
                "MenuGen: проверка отправки почты",
                "Если вы видите это письмо — отправка почты настроена корректно.",
                sender,
                [to],
                fail_silently=False,
            )
        except Exception as e:  # noqa: BLE001 — показываем причину как есть
            raise CommandError(f"Ошибка отправки: {e}") from e

        if sent:
            self.stdout.write(self.style.SUCCESS("Письмо отправлено ✅ Проверьте входящие и «Спам»."))
        else:
            raise CommandError("send_mail вернул 0 — письмо не отправлено.")
