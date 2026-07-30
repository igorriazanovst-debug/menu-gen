"""MG_PHONEVERIFY/max: long-polling воркер Max-бота (для dev без HTTPS).

Аналог run_telegram_bot, но под Max Bot API: события забираются через
``GET /updates`` с курсором ``marker``, токен идёт в заголовке Authorization.

Ограничения Max (важно): long-polling — 2 запроса в секунду, таймаут до 30 с,
события живут 24 часа. Для продакшена Max рекомендует webhook
(см. MaxWebhookView), polling оставляем для локальной отладки.

Запуск:  python manage.py run_max_bot
"""

import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.users.messengers import get_provider
from apps.users.messengers.handler import handle_update

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Long-polling Max-бота для подтверждения телефона (dev)."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=30, help="long-poll timeout, сек (макс. 30)")

    def handle(self, *args, **opts):
        token = getattr(settings, "MAX_BOT_TOKEN", "") or ""
        if not token:
            self.stderr.write("MAX_BOT_TOKEN не задан — нечего опрашивать.")
            return

        provider = get_provider("max")
        base = provider.api_base()
        long_poll = min(int(opts["timeout"]), 30)  # API не принимает больше 30
        marker = None
        self.stdout.write(f"Max API: {base}")
        self.stdout.write(self.style.SUCCESS("Max polling запущен. Ctrl+C для остановки."))

        while True:
            try:
                params = {"timeout": long_poll}
                if marker is not None:
                    params["marker"] = marker
                resp = requests.get(
                    f"{base}/updates",
                    params=params,
                    headers={"Authorization": token},
                    timeout=(10, long_poll + 15),
                )
                if resp.status_code != 200:
                    log.error("Max /updates HTTP %s: %s", resp.status_code, resp.text[:200])
                    time.sleep(3)
                    continue
                data = resp.json()
                for upd in data.get("updates", []):
                    handle_update(provider, upd)
                # Курсор следующего запроса; отсутствует — оставляем прежний.
                marker = data.get("marker", marker)
            except KeyboardInterrupt:  # pragma: no cover
                self.stdout.write("Остановлено.")
                break
            except requests.exceptions.Timeout:
                # Холостой long-poll без событий — норма, просто переспрашиваем.
                continue
            except requests.RequestException as e:
                log.error("Max polling error: %s", e)
                time.sleep(3)
