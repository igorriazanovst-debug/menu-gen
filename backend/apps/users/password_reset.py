"""MG_PWDRESET: восстановление пароля по ссылке из письма.

Устроено так же, как подтверждение e-mail (email_verify.py): подписанный токен
без отдельной модели, ссылка ведёт на страницу сайта, страница дёргает API.

Отличие одно, и оно существенное: в подпись кладётся отпечаток текущего пароля.
Голый TimestampSigner живёт до истечения срока и после смены пароля продолжает
работать — то есть письмо, украденное из почтового ящика, годилось бы второй раз
и после того, как хозяин уже сменил пароль. Отпечаток это закрывает: сменился
пароль — все выданные ссылки перестали открываться, включая только что
использованную.
"""

import hashlib
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

log = logging.getLogger(__name__)

_SALT = "mg-password-reset"
# Два часа, а не трое суток как у подтверждения регистрации: подтверждение
# читают когда дойдут руки, а сброс пароля человек делает здесь и сейчас.
# Чем короче окно, тем меньше цена доступа к чужому почтовому ящику.
_MAX_AGE = 60 * 60 * 2


def _password_fingerprint(user) -> str:
    """Короткий отпечаток текущего хеша пароля.

    Хеш целиком в токен не кладём: токен попадает в адресную строку, в историю
    браузера и в логи веб-сервера. Двенадцати символов sha256 достаточно, чтобы
    заметить смену пароля, и по ним нельзя восстановить сам хеш.
    """
    return hashlib.sha256((user.password or "").encode()).hexdigest()[:12]


def make_token(user) -> str:
    return TimestampSigner(salt=_SALT).sign(f"{user.id}:{_password_fingerprint(user)}")


def read_token(token: str):
    """Возвращает пользователя по валидному токену, иначе None.

    Проверяется и подпись со сроком, и то, что пароль с момента выдачи не
    менялся.
    """
    from apps.users.models import User

    try:
        raw = TimestampSigner(salt=_SALT).unsign(token or "", max_age=_MAX_AGE)
        user_id, fingerprint = raw.split(":", 1)
        user = User.objects.get(id=int(user_id))
    except (BadSignature, SignatureExpired, ValueError, TypeError, User.DoesNotExist):
        return None
    if fingerprint != _password_fingerprint(user):
        return None
    return user


def _frontend_base() -> str:
    import os

    base = getattr(settings, "FRONTEND_URL", "") or os.environ.get("BACKEND_PUBLIC_URL", "")
    return (base or "https://menugen.ru").rstrip("/")


def build_reset_link(user) -> str:
    return f"{_frontend_base()}/reset-password?token={make_token(user)}"


def send_reset_email(user) -> str:
    """Отправляет письмо (если почта настроена) и возвращает ссылку.

    Возвращает ссылку всегда — в DEBUG её отдаёт ответ API, чтобы сброс можно
    было проверить на dev, где почта не настроена.
    """
    link = build_reset_link(user)
    subject = "Восстановление пароля в MenuGen"
    body = (
        f"Здравствуйте, {user.name or ''}!\n\n"
        f"Кто-то запросил смену пароля для этого аккаунта. Чтобы задать новый пароль, "
        f"перейдите по ссылке:\n{link}\n\n"
        f"Ссылка действует 2 часа и срабатывает один раз.\n\n"
        f"Если вы этого не просили — просто игнорируйте письмо, пароль останется прежним."
    )
    from apps.common.mail import email_enabled

    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@menugen.ru"
    if email_enabled() and user.email:
        try:
            send_mail(subject, body, sender, [user.email], fail_silently=False)
        except Exception as e:  # не роняем ответ из-за почты
            log.error("send_reset_email failed for %s: %s", user.email, e)
    else:
        log.info("EMAIL not configured — reset link for %s: %s", user.email, link)
    return link
