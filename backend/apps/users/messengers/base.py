"""Базовый интерфейс провайдера мессенджера + фабрика."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContactShare:
    """Нормализованное событие «пользователь поделился контактом».

    Единый вид для Telegram и Max, чтобы обработчик не зависел от провайдера.
    """

    token: str  # значение из deep-link ?start=<token> (payload команды /start)
    chat_id: str  # куда отвечать
    from_user_id: str  # id отправителя апдейта
    contact_user_id: str | None  # id владельца контакта (для сверки «свой ли контакт»)
    contact_phone: str  # номер из контакта


class MessengerProvider:
    """Интерфейс провайдера. Конкретные реализации — telegram.py / max.py."""

    name: str = ""

    # ── настройка ────────────────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        """Настроен ли провайдер (есть токен бота) — можно ли слать запросы."""
        return bool(self._token())

    def _token(self) -> str:  # pragma: no cover - переопределяется
        raise NotImplementedError

    def bot_username(self) -> str:  # pragma: no cover - переопределяется
        raise NotImplementedError

    # ── deep-link ────────────────────────────────────────────────────────────
    def build_deep_link(self, token: str) -> str:  # pragma: no cover
        raise NotImplementedError

    # ── разбор входящих ──────────────────────────────────────────────────────
    def parse_start(self, update: dict):
        """Вернуть (chat_id, token) если это /start с payload, иначе None."""
        raise NotImplementedError

    def parse_contact(self, update: dict) -> ContactShare | None:
        """Вернуть ContactShare если апдейт содержит share-контакта, иначе None."""
        raise NotImplementedError

    # ── исходящие ────────────────────────────────────────────────────────────
    def send_request_contact(self, chat_id: str, text: str) -> None:
        """Сообщение с кнопкой «Поделиться номером»."""
        raise NotImplementedError

    def send_message(self, chat_id: str, text: str) -> None:
        """Обычное текстовое сообщение (убрать клавиатуру)."""
        raise NotImplementedError


_REGISTRY: dict[str, MessengerProvider] = {}


def get_provider(name: str) -> MessengerProvider:
    """Ленивая фабрика провайдера по имени (telegram/max)."""
    if name not in _REGISTRY:
        if name == "telegram":
            from .telegram import TelegramProvider

            _REGISTRY[name] = TelegramProvider()
        elif name == "max":
            from .max import MaxProvider

            _REGISTRY[name] = MaxProvider()
        else:
            raise ValueError(f"Неизвестный провайдер мессенджера: {name}")
    return _REGISTRY[name]
