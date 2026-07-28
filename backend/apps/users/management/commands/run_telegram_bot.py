"""MG_PHONEVERIFY: long-polling воркер Telegram-бота (для dev без HTTPS).

Telegram webhook требует публичный HTTPS, поэтому на dev получаем апдейты через
getUpdates. Прод использует webhook (TelegramWebhookView) — polling не нужен.

Запуск:  python manage.py run_telegram_bot
"""

import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.users.messengers import get_provider
from apps.users.messengers.handler import handle_update
from apps.users.messengers.telegram import API_BASE, telegram_proxies

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Long-polling Telegram-бота для подтверждения телефона (dev)."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=30, help="long-poll timeout, сек")

    def handle(self, *args, **opts):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        if not token:
            self.stderr.write("TELEGRAM_BOT_TOKEN не задан — нечего опрашивать.")
            return

        provider = get_provider("telegram")
        base = f"{API_BASE}/bot{token}"
        long_poll = int(opts["timeout"])
        offset = None
        proxies = telegram_proxies()
        if proxies:
            self.stdout.write(f"Через прокси: {proxies['https']}")
        self.stdout.write(self.style.SUCCESS("Telegram polling запущен. Ctrl+C для остановки."))

        while True:
            try:
                params = {"timeout": long_poll}
                if offset is not None:
                    params["offset"] = offset
                # (connect, read): read с запасом над long-poll. Через прокси
                # холостой long-poll иногда закрывается по таймауту — это норма,
                # не ошибка (см. обработку Timeout ниже).
                resp = requests.get(
                    f"{base}/getUpdates",
                    params=params,
                    timeout=(10, long_poll + 15),
                    proxies=proxies,
                )
                data = resp.json()
                if not data.get("ok"):
                    log.error("getUpdates не ok: %s", data)
                    time.sleep(3)
                    continue
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    handle_update(provider, upd)
            except KeyboardInterrupt:  # pragma: no cover
                self.stdout.write("Остановлено.")
                break
            except requests.exceptions.Timeout:
                # Холостой long-poll без новых сообщений — ожидаемо, просто
                # переспрашиваем. Не логируем как ошибку.
                continue
            except requests.RequestException as e:
                log.error("polling error: %s", e)
                time.sleep(3)
