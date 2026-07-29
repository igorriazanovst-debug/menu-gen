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
        to = opts["to"]
        host = getattr(settings, "EMAIL_HOST", "") or ""
        sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
        if not host:
            raise CommandError("EMAIL_HOST не задан — SMTP не настроен (см. .env).")

        proxy = getattr(settings, "EMAIL_PROXY", "") or ""
        self.stdout.write(
            f"SMTP {host}:{settings.EMAIL_PORT} "
            f"(TLS={settings.EMAIL_USE_TLS}, SSL={settings.EMAIL_USE_SSL}); от {sender} → {to}"
        )
        self.stdout.write(f"Прокси: {proxy or 'нет (напрямую)'}; backend={settings.EMAIL_BACKEND}")
        try:
            sent = send_mail(
                "MenuGen: проверка SMTP",
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
