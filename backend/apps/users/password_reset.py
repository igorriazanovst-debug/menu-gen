"""MG_PWDRESET: восстановление пароля по ссылке.

Каналов доставки два, и выбирает не пользователь, а то, чем он подтверждал
владение: у кого есть e-mail — письмом, у зарегистрировавшихся по телефону —
сообщением в тот мессенджер, где они делились контактом. Придумывать
телефонным аккаунтам отдельный способ не пришлось: доказательство владения
номером у нас уже есть, и это тот самый диалог с ботом.

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


def messenger_target(phone: str):
    """Где мы можем написать владельцу этого номера: (провайдер, чат) или None.

    Берём заявку на подтверждение номера, в которой человек уже делился
    контактом: именно она доказала, что номер его, и именно её чат — тот самый
    диалог с ботом. Ничего нового заводить не нужно, chat_id и провайдер
    хранятся там с самой регистрации.

    Годятся и verified, и consumed: заявка становится consumed сразу после
    завершения регистрации, то есть у зарегистрированного человека она как раз
    в этом состоянии. Свежая — на случай, если номер подтверждали повторно
    (например, сменив мессенджер): писать надо в последний известный диалог.
    """
    from apps.users.models import PhoneVerification

    from .phone_verify import normalize_phone

    norm = normalize_phone(phone)
    if not norm:
        return None
    return (
        PhoneVerification.objects.filter(
            phone=norm,
            status__in=(PhoneVerification.Status.VERIFIED, PhoneVerification.Status.CONSUMED),
            chat_id__isnull=False,
        )
        .exclude(chat_id="")
        .order_by("-created_at")
        .first()
    )


def send_reset_via_messenger(user) -> str | None:
    """Отправляет ссылку в мессенджер, где подтверждался номер.

    Возвращает ссылку, если было куда и через что писать, иначе None. Отправку
    не считаем обязанной удаться: бота могли заблокировать, а провайдер — быть
    выключенным на этом стенде. Ошибку логируем и молчим, потому что наружу
    ответ обязан быть одинаковым для всех номеров (см. PasswordResetRequestView).
    """
    from .messengers import get_provider

    pv = messenger_target(user.phone or "")
    if pv is None:
        return None

    try:
        provider = get_provider(pv.provider)
    except ValueError:  # провайдер из старой записи, которого больше нет в коде
        log.error("send_reset_via_messenger: неизвестный провайдер %r", pv.provider)
        return None
    if not provider.enabled:
        log.info("send_reset_via_messenger: провайдер %s выключен", pv.provider)
        return None

    link = build_reset_link(user)
    text = (
        "Кто-то запросил смену пароля в MenuGen для этого номера.\n\n"
        f"Чтобы задать новый пароль, откройте ссылку:\n{link}\n\n"
        "Ссылка действует 2 часа и срабатывает один раз. "
        "Если вы этого не просили — просто не открывайте её, пароль останется прежним."
    )
    try:
        provider.send_message(pv.chat_id, text)
    except Exception as e:  # не роняем ответ из-за мессенджера
        log.error("send_reset_via_messenger failed for %s: %s", pv.provider, e)
    return link
