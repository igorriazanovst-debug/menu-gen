"""Единый обработчик входящих апдейтов бота (webhook и long-polling).

Провайдеро-независим: получает провайдера и сырой update, применяет логику
подтверждения телефона и отвечает пользователю.
"""

from __future__ import annotations

import logging

from apps.users import phone_verify as pv_mod

from .base import MessengerProvider

log = logging.getLogger(__name__)

_MSG_ASK_CONTACT = "Чтобы подтвердить номер телефона, нажмите кнопку ниже и поделитесь своим контактом."
_MSG_BAD_TOKEN = "Ссылка недействительна или устарела. Вернитесь на сайт и начните подтверждение заново."
_MSG_NOT_OWN = "Пожалуйста, поделитесь именно своим контактом (кнопкой ниже)."
_MSG_MISMATCH = (
    "Этот номер не совпадает с тем, что вы ввели на сайте. Проверьте номер на сайте "
    "или используйте телефон, привязанный к этому аккаунту."
)
_MSG_VERIFIED = "Номер подтверждён ✅ Вернитесь на сайт, чтобы завершить регистрацию."
_MSG_EXPIRED = "Время подтверждения истекло. Начните заново на сайте."


def handle_update(provider: MessengerProvider, update: dict) -> None:
    """Обрабатывает один апдейт. Исключения логируются, не пробрасываются."""
    try:
        _handle(provider, update)
    except Exception:  # noqa: BLE001 - webhook/poller не должен падать на одном апдейте
        log.exception("Ошибка обработки апдейта %s", provider.name)


def _handle(provider: MessengerProvider, update: dict) -> None:
    # 1) /start <token> — привязываем чат к заявке и просим контакт.
    start = provider.parse_start(update)
    if start is not None:
        chat_id, token = start
        pv = pv_mod.bind_chat(token, chat_id) if token else None
        if pv is None:
            provider.send_message(chat_id, _MSG_BAD_TOKEN)
        else:
            provider.send_request_contact(chat_id, _MSG_ASK_CONTACT)
        return

    # 2) Пользователь поделился контактом.
    share = provider.parse_contact(update)
    if share is not None:
        pv = pv_mod.find_by_chat(share.chat_id)
        if pv is None:
            provider.send_message(share.chat_id, _MSG_BAD_TOKEN)
            return
        result = pv_mod.apply_shared_contact(
            pv,
            contact_phone=share.contact_phone,
            contact_user_id=share.contact_user_id,
            from_user_id=share.from_user_id,
        )
        if result == "verified":
            provider.send_message(share.chat_id, _MSG_VERIFIED)
        elif result == "rejected":
            provider.send_request_contact(share.chat_id, _MSG_NOT_OWN)
        elif result == "mismatch":
            provider.send_message(share.chat_id, _MSG_MISMATCH)
        elif result == "expired":
            provider.send_message(share.chat_id, _MSG_EXPIRED)
        return
