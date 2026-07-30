"""Max (max.ru) Bot API провайдер.

Интерфейс тот же, что у Telegram, поэтому общий обработчик (handler.py) и
эндпоинты подтверждения телефона не зависят от мессенджера.

Отличия Max от Telegram (сверено по официальной библиотеке max-botapi):
- база API ``https://platform-api2.max.ru``, токен в заголовке ``Authorization``;
- deep-link: ``https://max.ru/<bot>?start=<payload>``;
- старт бота приходит отдельным событием ``bot_started`` с полем ``payload``
  (а не текстовой командой ``/start``);
- контакт приходит вложением ``contact`` внутри ``message.body.attachments``,
  телефон лежит в vCard-строке ``vcf_info`` (поле ``TEL``), а владелец контакта —
  в ``payload.max_info.user_id`` (по нему сверяем, что контакт свой);
- события: ``GET /updates`` (long-polling, 2 RPS) либо webhook (для прода).
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from .base import ContactShare, MessengerProvider

log = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://platform-api2.max.ru"
_TIMEOUT = 15


def parse_vcf_phone(vcf_info: str) -> str:
    """Достаёт первый телефон из vCard-строки (поле ``TEL``).

    Пример строки: ``BEGIN:VCARD\\nTEL;TYPE=CELL:+7 912 345-67-89\\nEND:VCARD``.
    Параметры после ``;`` игнорируются, значение берётся после ``:``.
    """
    if not vcf_info:
        return ""
    for raw_line in vcf_info.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        name, _, value = line.partition(":")
        # "TEL" либо "TEL;TYPE=CELL" / "item1.TEL"
        key = name.split(";")[0].split(".")[-1].strip().upper()
        if key == "TEL" and value.strip():
            return value.strip()
    return ""


class MaxProvider(MessengerProvider):
    name = "max"

    def _token(self) -> str:
        return getattr(settings, "MAX_BOT_TOKEN", "") or ""

    def bot_username(self) -> str:
        return (getattr(settings, "MAX_BOT_USERNAME", "") or "").lstrip("@")

    def api_base(self) -> str:
        return (getattr(settings, "MAX_API_BASE", "") or DEFAULT_API_BASE).rstrip("/")

    def build_deep_link(self, token: str) -> str:
        # Токен заявки — url-safe, поэтому передаётся в payload как есть.
        return f"https://max.ru/{self.bot_username()}?start={token}"

    # ── разбор входящих ──────────────────────────────────────────────────────
    def parse_start(self, update: dict):
        """Старт бота: событие ``bot_started`` с payload из deep-link.

        Возвращает (chat_id, payload) либо None. Для совместимости также
        понимаем текстовую команду ``/start <payload>``.
        """
        upd = update or {}
        if upd.get("update_type") == "bot_started":
            chat_id = upd.get("chat_id")
            if chat_id is None:
                return None
            return (str(chat_id), (upd.get("payload") or "").strip())

        # Фолбэк: пользователь набрал /start вручную.
        message = upd.get("message") or {}
        text = ((message.get("body") or {}).get("text") or "").strip()
        if text.startswith("/start"):
            chat_id = (message.get("recipient") or {}).get("chat_id")
            if chat_id is None:
                return None
            parts = text.split(maxsplit=1)
            return (str(chat_id), parts[1].strip() if len(parts) > 1 else "")
        return None

    def parse_contact(self, update: dict) -> ContactShare | None:
        """Контакт: вложение ``contact`` в теле сообщения."""
        upd = update or {}
        message = upd.get("message") or {}
        body = message.get("body") or {}
        attachments = body.get("attachments") or []

        contact = next((a for a in attachments if (a or {}).get("type") == "contact"), None)
        if not contact:
            return None

        payload = contact.get("payload") or {}
        max_info = payload.get("max_info") or {}
        sender = message.get("sender") or {}
        chat_id = (message.get("recipient") or {}).get("chat_id")

        return ContactShare(
            token="",  # payload несёт только /start; заявку находим по chat_id
            chat_id=str(chat_id) if chat_id is not None else "",
            from_user_id=(str(sender.get("user_id")) if sender.get("user_id") is not None else ""),
            contact_user_id=(str(max_info.get("user_id")) if max_info.get("user_id") is not None else None),
            contact_phone=parse_vcf_phone(payload.get("vcf_info") or ""),
        )

    # ── исходящие ────────────────────────────────────────────────────────────
    def _post_message(self, chat_id: str, text: str, attachments: list | None = None) -> None:
        token = self._token()
        if not token:
            log.warning("MAX_BOT_TOKEN не задан — сообщение не отправлено")
            return
        url = f"{self.api_base()}/messages"
        payload: dict = {"text": text}
        if attachments:
            payload["attachments"] = attachments
        try:
            requests.post(
                url,
                params={"chat_id": chat_id},
                json=payload,
                headers={"Authorization": token},
                timeout=_TIMEOUT,
            )
        except requests.RequestException as e:  # не роняем обработку апдейта
            log.error("Max sendMessage failed: %s", e)

    def send_request_contact(self, chat_id: str, text: str) -> None:
        self._post_message(
            chat_id,
            text,
            attachments=[
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": [[{"type": "request_contact", "text": "📱 Поделиться номером"}]]},
                }
            ],
        )

    def send_message(self, chat_id: str, text: str) -> None:
        self._post_message(chat_id, text)
