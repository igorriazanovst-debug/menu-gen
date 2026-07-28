"""Max (max.ru) Bot API провайдер — ЗАГЛУШКА.

Интерфейс совпадает с Telegram, чтобы обработчик и эндпоинты не зависели от
провайдера. Конкретные методы Bot API Max (deep-link со стартовым payload,
запрос контакта/номера, формат webhook) нужно сверить по dev.max.ru и
дозаполнить. До этого провайдер выключен (enabled=False), а deep-link ведёт на
бота по username (payload-схему уточним при подключении).
"""

from __future__ import annotations

import logging

from django.conf import settings

from .base import ContactShare, MessengerProvider

log = logging.getLogger(__name__)


class MaxProvider(MessengerProvider):
    name = "max"

    def _token(self) -> str:
        return getattr(settings, "MAX_BOT_TOKEN", "") or ""

    def bot_username(self) -> str:
        return (getattr(settings, "MAX_BOT_USERNAME", "") or "").lstrip("@")

    def build_deep_link(self, token: str) -> str:
        # TODO(MG_PHONEVERIFY/max): сверить формат deep-link Max Bot API.
        user = self.bot_username()
        return f"https://max.ru/{user}?start={token}"

    def parse_start(self, update: dict):  # pragma: no cover - до подключения API
        raise NotImplementedError("Max provider not implemented yet")

    def parse_contact(self, update: dict) -> ContactShare | None:  # pragma: no cover
        raise NotImplementedError("Max provider not implemented yet")

    def send_request_contact(self, chat_id: str, text: str) -> None:  # pragma: no cover
        raise NotImplementedError("Max provider not implemented yet")

    def send_message(self, chat_id: str, text: str) -> None:  # pragma: no cover
        raise NotImplementedError("Max provider not implemented yet")
