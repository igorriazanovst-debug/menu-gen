"""MG_PHONEVERIFY: провайдеры мессенджеров для подтверждения телефона.

Единый интерфейс поверх Telegram и Max: построить deep-link на бота, разобрать
входящий update, попросить пользователя поделиться контактом, отправить текст.
"""

from .base import ContactShare, MessengerProvider, get_provider

__all__ = ["ContactShare", "MessengerProvider", "get_provider"]
