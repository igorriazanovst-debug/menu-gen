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
    """Ключ целиком не пишем: начало, длина, хвост.

    Начало — не секрет и решает половину вопросов: у каждого сервиса свой
    префикс (`sk-aitunnel-`, `sk-proj-`, `AQVN`), и по нему сразу видно, тот ли
    это вообще ключ. Хвост нужен, чтобы отличить старый ключ от нового, когда
    контейнер поднялся со старым окружением.
    """
    if not value:
        return "не задан"
    if len(value) < 12:
        return "задан, но подозрительно короткий (%d символов)" % len(value)
    return "задан (%s…%s, %d символов)" % (value[:11], value[-4:], len(value))


class Command(BaseCommand):
    help = "MG_AIPING: проверить доступность ИИ-провайдера и показать конфигурацию."

    def add_arguments(self, parser):
        parser.add_argument("--prompt", default=PROMPT, help="Свой текст запроса.")
        # MG_AIEMPTY: 20 токенов хватало обычной модели, но не рассуждателю:
        # он тратит лимит на размышление и возвращает пустой текст при HTTP 200.
        parser.add_argument("--max-tokens", type=int, default=256)

    def handle(self, *args, **opts):
        from decouple import config

        provider = config("AI_PROVIDER", default="yandex")
        self.stdout.write("AI_PROVIDER:   %s" % provider)
        self.stdout.write("AI_TEXT_MODEL: %s" % config("AI_TEXT_MODEL", default="(по умолчанию провайдера)"))
        self.stdout.write("AI_BASE_URL:   %s" % config("AI_BASE_URL", default="(по умолчанию провайдера)"))
        self.stdout.write("AI_TIMEOUT:    %s" % config("AI_TIMEOUT", default="30"))
        # MG_AITIMEOUT: пакетная канонизация живёт на своих настройках. Показываем
        # их рядом: тяжёлая модель в AI_TEXT_MODEL бьёт по пользовательским путям
        # (скан штрих-кода, фото, список покупок), а не только по разовым прогонам.
        self.stdout.write("AI_CANON_MODEL:   %s" % (config("AI_CANON_MODEL", default="") or "(как AI_TEXT_MODEL)"))
        self.stdout.write("AI_CANON_TIMEOUT: %s" % config("AI_CANON_TIMEOUT", default="120"))
        self.stdout.write("AI_API_KEY:    %s" % mask(config("AI_API_KEY", default="")))
        if provider.strip().lower() == "yandex":
            self.stdout.write("AI_FOLDER_ID:  %s" % (config("AI_FOLDER_ID", default="") or "не задан"))

        # Куда реально уйдёт запрос: опечатка в base_url (потерянный /v1) даёт
        # ошибку, которую по тексту от сервиса не опознать.
        if provider.strip().lower() in ("openai", "yandex"):
            base = config(
                "AI_BASE_URL",
                default=(
                    "https://api.openai.com/v1"
                    if provider.strip().lower() == "openai"
                    else "https://llm.api.cloud.yandex.net/v1"
                ),
            )
            self.stdout.write("URL запроса:   %s/chat/completions" % base.rstrip("/"))

        # Ключ мог приехать в контейнер с переносом строки или пробелом на конце —
        # заголовок Authorization тогда битый, а на глаз это не видно.
        key = config("AI_API_KEY", default="")
        if key != key.strip():
            self.stdout.write(self.style.WARNING("ВНИМАНИЕ: в ключе есть пробелы или перенос строки по краям."))
        self.stdout.write("")

        self.ask("AI_TEXT_MODEL", None, None, opts)

        # MG_AIEMPTY: модель канонизации — отдельная настройка, и ломается она
        # отдельно. Проверять надо обе: пользовательские пути живут на одной,
        # долгий прогон по каталогу — на другой, и зелёная проверка первой
        # ничего не говорит про вторую.
        canon_model = (config("AI_CANON_MODEL", default="") or "").strip()
        if canon_model and canon_model != (config("AI_TEXT_MODEL", default="") or "").strip():
            self.ask(
                "AI_CANON_MODEL",
                canon_model,
                config("AI_CANON_TIMEOUT", default=120.0, cast=float),
                opts,
            )

    def ask(self, label, model, timeout, opts):
        """Один настоящий запрос указанной моделью, с замером времени."""
        from apps.common.ai_provider import get_ai_client

        try:
            client = get_ai_client(model=model, timeout=timeout)
        except Exception as exc:
            raise CommandError("%s: клиент не собрался — %s: %s" % (label, type(exc).__name__, exc))

        started = time.monotonic()
        try:
            answer = client.complete(prompt=opts["prompt"], system="", max_tokens=opts["max_tokens"], temperature=0.0)
        except Exception as exc:
            spent = time.monotonic() - started
            raise CommandError("%s: запрос не прошёл за %.1f с — %s: %s" % (label, spent, type(exc).__name__, exc))

        spent = time.monotonic() - started
        text = (answer or "").strip()
        if not text:
            raise CommandError("%s: пустой текст за %.1f с — это тоже отказ." % (label, spent))

        self.stdout.write(self.style.SUCCESS("%s — ответ за %.1f с: %s" % (label, spent, text[:200])))
