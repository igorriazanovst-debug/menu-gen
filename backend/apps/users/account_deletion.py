"""MG_ACCDEL: удаление аккаунта по требованию пользователя.

Требование Google Play: приложение, которое даёт завести аккаунт, обязано дать
и удалить его — изнутри приложения И по публичному веб-адресу, доступному без
входа. Без этого обновление в Play не публикуется вовсе.

Устройство в двух словах: удаление не мгновенное. Запрос замораживает аккаунт
(is_active=False + отметка времени), а данные стираются по расписанию через
GRACE_DAYS суток. Отменяется обычным входом — единственное, что замороженный
аккаунт ещё умеет.

Почему заморозка, а не немедленное стирание:

  * год дневника веса уходит одним нажатием, и вернуть его неоткуда — ни
    пользователю, ни поддержке;
  * захваченный аккаунт нельзя было бы спасти: злоумышленник удаляет, владелец
    узнаёт через неделю, возвращать нечего.

Play такую отсрочку разрешает при условии, что срок указан в форме Data safety.

Почему заморозка сделана через is_active, а не отдельной проверкой: этот флаг
уже смотрят и вход (LoginSerializer), и JWT (SimpleJWT проверяет is_active в
get_user), и админка. Любой другой способ пришлось бы вспоминать в каждой новой
точке входа — и однажды не вспомнить.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)

# Сколько аккаунт лежит замороженным до необратимого стирания.
GRACE_DAYS = getattr(settings, "ACCOUNT_DELETION_GRACE_DAYS", 30)

_SALT = "mg-account-delete"
# Ссылка из письма живёт сутки: она сама по себе — команда на удаление, и
# лежать в почтовом ящике неделями ей незачем.
_MAX_AGE = 60 * 60 * 24


def purge_after(requested_at):
    """Момент, начиная с которого запрос можно исполнять необратимо."""
    return requested_at + timedelta(days=GRACE_DAYS)


# --- ссылка для веб-формы (удаление без входа в приложение) ------------------


def make_token(user) -> str:
    return TimestampSigner(salt=_SALT).sign(str(user.id))


def read_token(token: str):
    """user_id из валидного токена, иначе None."""
    try:
        return int(TimestampSigner(salt=_SALT).unsign(token or "", max_age=_MAX_AGE))
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def _frontend_base() -> str:
    import os

    base = getattr(settings, "FRONTEND_URL", "") or os.environ.get("BACKEND_PUBLIC_URL", "")
    return (base or "https://menugen.ru").rstrip("/")


def build_confirm_link(user) -> str:
    return f"{_frontend_base()}/delete-account/confirm?token={make_token(user)}"


def send_confirmation_email(user) -> str:
    """Письмо со ссылкой-подтверждением. Возвращает ссылку (в DEBUG её отдаём в ответе)."""
    from django.core.mail import send_mail

    from apps.common.mail import email_enabled

    link = build_confirm_link(user)
    subject = "Удаление аккаунта MenuGen"
    body = (
        f"Здравствуйте, {user.name or ''}!\n\n"
        f"Мы получили запрос на удаление вашего аккаунта MenuGen.\n\n"
        f"Чтобы подтвердить удаление, перейдите по ссылке:\n{link}\n\n"
        f"Ссылка действует сутки.\n\n"
        f"После подтверждения аккаунт будет заблокирован, а данные удалены "
        f"через {GRACE_DAYS} дней. До этого срока удаление можно отменить — "
        f"просто войдите в приложение обычным способом.\n\n"
        f"Если вы не запрашивали удаление — ничего делать не нужно, просто "
        f"проигнорируйте это письмо."
    )
    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@menugen.ru"
    if email_enabled() and user.email:
        try:
            send_mail(subject, body, sender, [user.email], fail_silently=False)
        except Exception as e:  # почта не должна ронять запрос
            log.error("send_confirmation_email failed for user %s: %s", user.id, e)
    else:
        log.info("EMAIL not configured — delete link for user %s: %s", user.id, link)
    return link


# --- запрос, отмена, исполнение ---------------------------------------------


@transaction.atomic
def request_deletion(user):
    """Заморозить аккаунт и назначить срок стирания. Идемпотентно.

    Ничего необратимого здесь НЕ происходит — в том числе не передаётся
    владение семьёй. Смысл отсрочки в том, чтобы отмена возвращала ровно то же
    состояние, а вернуть владение назад нечем: сменить владельца семьи через
    API нельзя, поле read-only. Поэтому передача отложена до стирания.

    Цена решения: пока глава семьи заморожен, действия «только для главы»
    (состав семьи, её настройки) недоступны остальным участникам — до отмены
    или до конца отсрочки. Своими данными участники продолжают пользоваться.
    """
    if user.deletion_requested_at is None:
        user.deletion_requested_at = timezone.now()
        user.is_active = False
        user.save(update_fields=["deletion_requested_at", "is_active"])
        log.info(
            "MG_ACCDEL: удаление запрошено, user=%s, стирание после %s",
            user.id,
            purge_after(user.deletion_requested_at),
        )
    return purge_after(user.deletion_requested_at)


@transaction.atomic
def cancel_deletion(user) -> bool:
    """Разморозить аккаунт. True — отмена действительно произошла."""
    if user.deletion_requested_at is None:
        return False
    user.deletion_requested_at = None
    user.is_active = True
    user.save(update_fields=["deletion_requested_at", "is_active"])
    log.info("MG_ACCDEL: удаление отменено, user=%s", user.id)
    return True


def _pick_heir(family, leaving):
    """Кому достаётся семья. None — наследовать некому.

    Управляемые участники (`is_managed` — дети и подопечные без своего входа)
    наследовать не могут: у них нет пароля, войти и распорядиться семьёй некому.
    """
    from apps.family.models import FamilyMember

    return (
        FamilyMember.objects.filter(family=family)
        .exclude(user=leaving)
        .exclude(user__is_managed=True)
        .exclude(user__deletion_requested_at__isnull=False)
        .select_related("user")
        .order_by("joined_at", "id")
        .values_list("user", flat=True)
        .first()
    )


@transaction.atomic
def purge_user(user) -> dict:
    """Необратимо удалить пользователя. Возвращает отчёт о том, что сделано.

    Семьи, которыми он владел, достаются старшему из оставшихся участников.
    Если наследовать некому — семья удаляется вместе со своими данными (меню,
    холодильник, дневники), а вместе с ней и управляемые участники, для которых
    эта семья была единственной: без неё такой аккаунт — строка, в которую
    нельзя войти и которая ни на что не ссылается.

    Платежи переживают удаление намеренно: это бухгалтерская запись о
    состоявшейся сделке, её сверяют с ЮKassa. Личных данных в ней нет — только
    сумма, дата и идентификатор платежа у провайдера, — а ссылка на семью
    обнуляется (payments.family → SET_NULL, см. миграцию).
    """
    from apps.family.models import Family, FamilyMember

    report = {"user_id": user.id, "families_transferred": 0, "families_deleted": 0, "managed_deleted": 0}

    for family in Family.objects.filter(owner=user):
        heir_id = _pick_heir(family, leaving=user)
        if heir_id:
            family.owner_id = heir_id
            family.save(update_fields=["owner"])
            FamilyMember.objects.filter(family=family, user_id=heir_id).update(role=FamilyMember.Role.HEAD)
            report["families_transferred"] += 1
            continue

        managed_ids = list(
            FamilyMember.objects.filter(family=family, user__is_managed=True)
            .exclude(user=user)
            .values_list("user_id", flat=True)
        )
        family.delete()
        for managed_id in managed_ids:
            if not FamilyMember.objects.filter(user_id=managed_id).exists():
                type(user).objects.filter(id=managed_id).delete()
                report["managed_deleted"] += 1
        report["families_deleted"] += 1

    user.delete()
    log.info("MG_ACCDEL: аккаунт стёрт, %s", report)
    return report


def due_for_purge(now=None):
    """Пользователи, чья отсрочка истекла."""
    from apps.users.models import User

    now = now or timezone.now()
    return User.objects.filter(
        deletion_requested_at__isnull=False, deletion_requested_at__lte=now - timedelta(days=GRACE_DAYS)
    )
