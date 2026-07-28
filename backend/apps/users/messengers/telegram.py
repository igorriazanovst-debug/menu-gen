"""Telegram Bot API провайдер.

Deep-link: ``https://t.me/<bot>?start=<token>`` → бот получает ``/start <token>``.
Кнопка ``request_contact`` возвращает контакт с ``user_id`` владельца — по нему
сверяем, что пользователь поделился именно своим номером.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from .base import ContactShare, MessengerProvider

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
_TIMEOUT = 10


def telegram_proxies():
    """proxies-словарь для requests, если задан TELEGRAM_PROXY (иначе None).

    В РФ api.telegram.org часто заблокирован — трафик к нему пускаем через
    внешний прокси (напр. локальный SOCKS5 от Xray-клиента с VLESS/Reality).
    Пример значения: ``socks5h://xray:1080`` (h — DNS резолвится на стороне
    прокси, важно при блокировке/подмене DNS). Требует PySocks для socks5.
    """
    proxy = getattr(settings, "TELEGRAM_PROXY", "") or ""
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


class TelegramProvider(MessengerProvider):
    name = "telegram"

    def _token(self) -> str:
        return getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""

    def bot_username(self) -> str:
        return (getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").lstrip("@")

    def build_deep_link(self, token: str) -> str:
        user = self.bot_username()
        return f"https://t.me/{user}?start={token}"

    # ── разбор входящих ──────────────────────────────────────────────────────
    def parse_start(self, update: dict):
        msg = (update or {}).get("message") or {}
        text = msg.get("text") or ""
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None or not text.startswith("/start"):
            return None
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        return (str(chat_id), payload)

    def parse_contact(self, update: dict) -> ContactShare | None:
        msg = (update or {}).get("message") or {}
        contact = msg.get("contact")
        if not contact:
            return None
        chat = msg.get("chat") or {}
        from_user = msg.get("from") or {}
        return ContactShare(
            token="",  # Telegram не возвращает payload с контактом — берём по chat_id
            chat_id=str(chat.get("id")),
            from_user_id=str(from_user.get("id")) if from_user.get("id") is not None else "",
            contact_user_id=(str(contact.get("user_id")) if contact.get("user_id") is not None else None),
            contact_phone=contact.get("phone_number") or "",
        )

    # ── исходящие ────────────────────────────────────────────────────────────
    def _call(self, method: str, payload: dict) -> None:
        token = self._token()
        if not token:
            log.warning("TELEGRAM_BOT_TOKEN не задан — пропуск %s", method)
            return
        url = f"{API_BASE}/bot{token}/{method}"
        try:
            requests.post(url, json=payload, timeout=_TIMEOUT, proxies=telegram_proxies())
        except requests.RequestException as e:  # не роняем обработку апдейта
            log.error("Telegram %s failed: %s", method, e)

    def send_request_contact(self, chat_id: str, text: str) -> None:
        self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {
                    "keyboard": [[{"text": "📱 Поделиться номером", "request_contact": True}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                },
            },
        )

    def send_message(self, chat_id: str, text: str) -> None:
        self._call(
            "sendMessage",
            {"chat_id": chat_id, "text": text, "reply_markup": {"remove_keyboard": True}},
        )
