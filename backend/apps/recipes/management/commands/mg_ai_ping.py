"""MG_AIPING: жив ли сейчас ИИ-провайдер и на какой конфигурации мы работаем.

Понадобилось вот почему. Канонизация состава (`recipe_products`) спрашивает
модель пачками и на ошибку чанка молча ставит «ответа нет»: провайдер лежит —
прогон всё равно доходит до конца, просто половина названий остаётся сырой.
Отличить «модель не поняла ингредиент» от «до модели не достучались» по
результату нельзя, поэтому нужен отдельный способ спросить напрямую.

Команда показывает конфигурацию (ключ — только признаком, не значением) и
делает один настоящий запрос с замером времени.

    docker compose exec -T backend python manage.py mg_ai_ping
"""

import time

from django.core.management.base import BaseCommand, CommandError

# Короткий вопрос с однозначным ответом: проверяем доступность, а не качество.
PROMPT = "Ответь одним словом: столица России?"


def mask(value):
    """Ключ в вывод не пишем — только длину и хвост, чтобы отличить два ключа."""
    if not value:
        return "не задан"
    return "задан (%d символов, …%s)" % (len(value), value[-4:])


class Command(BaseCommand):
    help = "MG_AIPING: проверить доступность ИИ-провайдера и показать конфигурацию."

    def add_arguments(self, parser):
        parser.add_argument("--prompt", default=PROMPT, help="Свой текст запроса.")
        parser.add_argument("--max-tokens", type=int, default=20)

    def handle(self, *args, **opts):
        from decouple import config

        provider = config("AI_PROVIDER", default="yandex")
        self.stdout.write("AI_PROVIDER:   %s" % provider)
        self.stdout.write("AI_TEXT_MODEL: %s" % config("AI_TEXT_MODEL", default="(по умолчанию провайдера)"))
        self.stdout.write("AI_BASE_URL:   %s" % config("AI_BASE_URL", default="(по умолчанию провайдера)"))
        self.stdout.write("AI_TIMEOUT:    %s" % config("AI_TIMEOUT", default="30"))
        self.stdout.write("AI_API_KEY:    %s" % mask(config("AI_API_KEY", default="")))
        if provider.strip().lower() == "yandex":
            self.stdout.write("AI_FOLDER_ID:  %s" % (config("AI_FOLDER_ID", default="") or "не задан"))
        self.stdout.write("")

        from apps.common.ai_provider import get_ai_client

        try:
            client = get_ai_client()
        except Exception as exc:
            raise CommandError("Клиент не собрался: %s: %s" % (type(exc).__name__, exc))

        started = time.monotonic()
        try:
            answer = client.complete(prompt=opts["prompt"], system="", max_tokens=opts["max_tokens"], temperature=0.0)
        except Exception as exc:
            spent = time.monotonic() - started
            raise CommandError("Запрос не прошёл за %.1f с — %s: %s" % (spent, type(exc).__name__, exc))

        spent = time.monotonic() - started
        text = (answer or "").strip()
        if not text:
            raise CommandError("Провайдер ответил пустым текстом за %.1f с — это тоже отказ." % spent)

        self.stdout.write(self.style.SUCCESS("Ответ за %.1f с: %s" % (spent, text[:200])))
