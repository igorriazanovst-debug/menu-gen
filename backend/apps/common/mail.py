"""MG_MAILAPI: определение того, настроена ли отправка почты.

Раньше код проверял просто ``settings.EMAIL_HOST`` — это верно только для SMTP.
При отправке через HTTP API провайдера (Anymail: Unisender Go и др.) SMTP-хост
не нужен и остаётся пустым, поэтому проверка должна зависеть от бэкенда.
"""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def email_enabled() -> bool:
    """Можно ли реально отправить письмо с текущими настройками.

    - SMTP-бэкенд (в т.ч. наш ProxyEmailBackend) — нужен EMAIL_HOST;
    - HTTP-API бэкенды (Anymail) — хост не нужен, ключ проверяет сам бэкенд;
    - console/locmem/filebased (dev, тесты) — «отправка» всегда доступна.
    """
    from django.core.mail import get_connection
    from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend

    try:
        connection = get_connection(fail_silently=True)
    except Exception as e:  # неверный путь бэкенда и пр.
        log.error("email_enabled: не удалось создать connection: %s", e)
        return False

    if isinstance(connection, SmtpEmailBackend):
        return bool(getattr(settings, "EMAIL_HOST", ""))
    return True
