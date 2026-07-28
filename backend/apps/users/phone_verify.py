"""MG_PHONEVERIFY: подтверждение владения телефоном через бот мессенджера.

В отличие от e-mail (подписанный токен без модели), здесь нужна модель
``PhoneVerification``: бот приходит асинхронно, статус хранится и опрашивается
с сайта, а номер из мессенджера сверяется с введённым на сайте.
"""

import logging
import re
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import PhoneVerification, User

log = logging.getLogger(__name__)

# Сколько живёт заявка на подтверждение (не подтвердил — протухла).
VERIFY_TTL = timedelta(minutes=30)
# Максимум попыток «поделиться контактом» на одну заявку (анти-перебор).
MAX_ATTEMPTS = 5


def normalize_phone(raw: str) -> str:
    """Приводит номер к каноничному виду ``+7XXXXXXXXXX`` (РФ) / ``+<digits>``.

    - убираются все нецифры, кроме ведущего ``+``;
    - российские ``8XXXXXXXXXX`` → ``+7XXXXXXXXXX``;
    - 10 цифр (без кода страны) → трактуем как РФ, добавляем ``+7``.
    Формат сравнения — только цифры с ведущим ``+``; для внешнего сравнения
    важна идентичность строк, а не полный E.164-парсинг.
    """
    if not raw:
        return ""
    s = raw.strip()
    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    if not has_plus:
        if len(digits) == 11 and digits[0] == "8":
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
    else:
        # уже с +; РФ-номера иногда приходят как +8... — нормализуем
        if len(digits) == 11 and digits[0] == "8":
            digits = "7" + digits[1:]
    return "+" + digits


def phones_match(a: str, b: str) -> bool:
    """Сравнение двух номеров после нормализации."""
    return bool(a) and normalize_phone(a) == normalize_phone(b)


def _gen_token() -> str:
    # url-safe, короткий, непредсказуемый; годится для deep-link ?start=
    return secrets.token_urlsafe(24)


def create_verification(phone: str, provider: str) -> PhoneVerification:
    """Создаёт новую заявку на подтверждение телефона.

    Старые pending-заявки на тот же номер помечаются expired, чтобы на номер
    была активна только одна заявка.
    """
    norm = normalize_phone(phone)
    PhoneVerification.objects.filter(phone=norm, status=PhoneVerification.Status.PENDING).update(
        status=PhoneVerification.Status.EXPIRED
    )
    return PhoneVerification.objects.create(
        phone=norm,
        provider=provider,
        token=_gen_token(),
        status=PhoneVerification.Status.PENDING,
        expires_at=timezone.now() + VERIFY_TTL,
    )


def get_active(token: str):
    """Возвращает не-протухшую заявку по token, иначе None.

    Протухшую по времени pending-заявку помечает expired.
    """
    if not token:
        return None
    pv = PhoneVerification.objects.filter(token=token).first()
    if pv is None:
        return None
    if pv.status == PhoneVerification.Status.PENDING and pv.is_expired:
        pv.status = PhoneVerification.Status.EXPIRED
        pv.save(update_fields=["status"])
    return pv


def phone_taken(phone: str) -> bool:
    """Уже есть аккаунт с таким телефоном?"""
    return User.objects.filter(phone=normalize_phone(phone)).exists()


def bind_chat(token: str, chat_id) -> PhoneVerification | None:
    """Привязывает чат мессенджера к заявке (по token из /start).

    Возвращает заявку, если токен валиден и она активна, иначе None.
    """
    pv = get_active(token)
    if pv is None or pv.status != PhoneVerification.Status.PENDING:
        return None
    pv.chat_id = str(chat_id)
    pv.save(update_fields=["chat_id"])
    return pv


def find_by_chat(chat_id) -> PhoneVerification | None:
    """Ищет активную заявку по привязанному чату (для контакт-сообщения)."""
    if chat_id is None:
        return None
    return (
        PhoneVerification.objects.filter(
            chat_id=str(chat_id),
            status__in=[PhoneVerification.Status.PENDING, PhoneVerification.Status.MISMATCH],
        )
        .order_by("-created_at")
        .first()
    )


def apply_shared_contact(pv: PhoneVerification, *, contact_phone: str, contact_user_id, from_user_id) -> str:
    """Обрабатывает контакт, которым пользователь поделился в боте.

    Возвращает новый статус заявки:
    - ``verified``  — контакт свой (contact_user_id == from_user_id) и номер совпал;
    - ``mismatch``  — поделился своим контактом, но номер не совпал с введённым;
    - ``rejected``  — поделился чужим контактом (contact_user_id != from_user_id).

    Заявка сохраняется. Идемпотентно для уже завершённых заявок.
    """
    if pv.status not in (PhoneVerification.Status.PENDING, PhoneVerification.Status.MISMATCH):
        return pv.status

    pv.attempts = (pv.attempts or 0) + 1
    pv.messenger_user_id = str(contact_user_id) if contact_user_id is not None else None
    pv.messenger_phone = normalize_phone(contact_phone)

    # Чужой контакт — не доказывает владение номером.
    if contact_user_id is None or from_user_id is None or str(contact_user_id) != str(from_user_id):
        pv.save(update_fields=["attempts", "messenger_user_id", "messenger_phone"])
        return "rejected"

    if pv.is_expired:
        pv.status = PhoneVerification.Status.EXPIRED
        pv.save(update_fields=["status", "attempts", "messenger_user_id", "messenger_phone"])
        return pv.status

    if phones_match(pv.phone, contact_phone):
        pv.status = PhoneVerification.Status.VERIFIED
        pv.verified_at = timezone.now()
        pv.save(update_fields=["status", "verified_at", "attempts", "messenger_user_id", "messenger_phone"])
        return "verified"

    pv.status = PhoneVerification.Status.MISMATCH
    pv.save(update_fields=["status", "attempts", "messenger_user_id", "messenger_phone"])
    return "mismatch"
