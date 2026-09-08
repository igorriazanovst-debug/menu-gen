"""MG_FAMINVITE: как приглашение доходит до человека.

Каналов три, и они не заменяют, а дополняют друг друга:

* запись в `Notification` — она видна в вебе и переживёт то, что человек в
  момент приглашения не держал приложение открытым;
* письмо — если у аккаунта есть подтверждённая почта;
* сообщение в мессенджер — если человек регистрировался по телефону и
  подтверждал его в диалоге с ботом. Тот же канал, что у восстановления пароля
  (`apps/users/password_reset.py`), и по той же причине: другого доказательства
  владения номером у нас нет, а этот диалог уже есть.

Пушей в проекте нет вовсе: `flutter_local_notifications` умеет только локальные
напоминания, а серверные уведомления мобильное приложение не показывает. Поэтому
на телефоне приглашение увидят при следующем открытии приложения — либо раньше,
письмом или сообщением от бота.

Ни один канал не считается обязанным сработать: почта может быть не настроена на
стенде, бота могли заблокировать. Ошибки логируем и молчим — приглашение уже
создано в базе, и человек увидит его, когда откроет приложение. Ронять ответ
главе семьи из-за недоехавшего письма нельзя: он решит, что не пригласил, и
нажмёт ещё раз.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

log = logging.getLogger(__name__)


def _family_label(family) -> str:
    return family.name or "семью"


def _text(invite) -> tuple[str, str]:
    """Заголовок и тело — одни на все каналы, чтобы не расходились."""
    who = (invite.invited_by.name if invite.invited_by else "") or "Глава семьи"
    title = "Приглашение в семью"
    body = (
        f"{who} приглашает вас в «{_family_label(invite.family)}» в MenuGen.\n\n"
        "Если примете — у вас станут общими холодильник, список покупок и меню, "
        "а глава семьи сможет видеть и менять ваши нормы КБЖУ. Личное останется "
        "вашим: дневник питания, вода и вес принадлежат вам, а не семье.\n\n"
        "Открыть приложение и ответить: Профиль → Семья.\n"
        "Пока вы не ответили, ничего не меняется."
    )
    return title, body


def notify_invited(invite) -> None:
    """Сообщить человеку, что его зовут. Ошибки каналов не пробрасываются."""
    title, body = _text(invite)
    user = invite.invited_user

    _notification(user, title, body)
    _email(user, title, body)
    _messenger(user, f"{title}\n\n{body}")


def _notification(user, title, body) -> None:
    try:
        from apps.notifications.models import Notification

        Notification.objects.create(
            user=user,
            notification_type=Notification.Type.SYSTEM,
            title=title,
            message=body,
            action_url="/family/",
        )
    except Exception as e:
        log.error("MG_FAMINVITE: не удалось записать уведомление для %s: %s", user.id, e)


def _email(user, subject, body) -> None:
    if not user.email:
        return
    from apps.common.mail import email_enabled

    if not email_enabled():
        log.info("MG_FAMINVITE: почта не настроена, приглашение для %s только в приложении", user.email)
        return
    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@menugen.ru"
    try:
        send_mail(subject, body, sender, [user.email], fail_silently=False)
    except Exception as e:
        log.error("MG_FAMINVITE: письмо для %s не ушло: %s", user.email, e)


def _messenger(user, text) -> None:
    from apps.users.messengers.base import get_provider
    from apps.users.password_reset import messenger_target

    pv = messenger_target(user.phone or "")
    if pv is None:
        return
    try:
        provider = get_provider(pv.provider)
    except ValueError:  # провайдер из старой записи, которого больше нет в коде
        log.error("MG_FAMINVITE: неизвестный провайдер %r", pv.provider)
        return
    if not provider.enabled:
        log.info("MG_FAMINVITE: провайдер %s выключен", pv.provider)
        return
    try:
        provider.send_message(pv.chat_id, text)
    except Exception as e:
        log.error("MG_FAMINVITE: сообщение через %s не ушло: %s", pv.provider, e)
