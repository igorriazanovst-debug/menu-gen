"""MG_EMAILVERIFY: подтверждение e-mail по ссылке из письма.

Токен — подписанный (TimestampSigner), без отдельной модели. Ссылка ведёт на
веб-страницу /verify-email?token=..., которая дёргает API подтверждения.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

log = logging.getLogger(__name__)

_SALT = "mg-email-verify"
_MAX_AGE = 60 * 60 * 24 * 3  # 3 суток


def make_token(user) -> str:
    return TimestampSigner(salt=_SALT).sign(str(user.id))


def read_token(token: str):
    """Возвращает user_id из валидного токена, иначе None."""
    try:
        raw = TimestampSigner(salt=_SALT).unsign(token, max_age=_MAX_AGE)
        return int(raw)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def _frontend_base() -> str:
    import os

    base = getattr(settings, "FRONTEND_URL", "") or os.environ.get("BACKEND_PUBLIC_URL", "")
    return (base or "https://menugen.ru").rstrip("/")


def build_verify_link(user) -> str:
    return f"{_frontend_base()}/verify-email?token={make_token(user)}"


def send_verification_email(user) -> str:
    """Отправляет письмо (если SMTP настроен) и возвращает ссылку.

    Если SMTP не настроен (dev), просто логируем ссылку — реальная отправка не
    выполняется. Ссылка возвращается вызывающему коду (в DEBUG её отдаём в ответе).
    """
    link = build_verify_link(user)
    subject = "Подтверждение регистрации в MenuGen"
    body = (
        f"Здравствуйте, {user.name or ''}!\n\n"
        f"Подтвердите ваш e-mail, перейдя по ссылке:\n{link}\n\n"
        f"Ссылка действует 3 дня. Если вы не регистрировались — просто игнорируйте это письмо."
    )
    # MG_MAILAPI: раньше здесь проверялся EMAIL_HOST, но при отправке через
    # HTTP API провайдера (Anymail) SMTP-хост пуст — нужна проверка по бэкенду.
    from apps.common.mail import email_enabled

    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@menugen.ru"
    if email_enabled() and user.email:
        try:
            send_mail(subject, body, sender, [user.email], fail_silently=False)
        except Exception as e:  # не роняем регистрацию из-за почты
            log.error("send_verification_email failed for %s: %s", user.email, e)
    else:
        log.info("EMAIL not configured — verify link for %s: %s", user.email, link)
    return link


def mark_verified(user) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
