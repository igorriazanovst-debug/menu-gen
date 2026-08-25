"""MG_ADMINRU: админка всегда по-русски.

`LocaleMiddleware` выбирает язык по заголовку `Accept-Language`, то есть по
настройкам браузера редактора. У браузера с английским в предпочтениях админка
открывалась по-английски целиком — при полностью переведённом каталоге и
`LANGUAGE_CODE = "ru-ru"`. Догадаться, почему «опять всё на английском»,
по интерфейсу невозможно.

Язык фиксируем только для `/admin/`: у API язык запроса выбирает клиент, и
отбирать у него эту возможность ради админки было бы слишком.

Middleware ставится ПОСЛЕ `LocaleMiddleware` — та уже выбрала язык, а мы для
админских путей перебиваем её выбор.
"""

from django.conf import settings
from django.utils import translation

ADMIN_LANGUAGE = "ru"


class AdminRussianLocaleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        prefix = getattr(settings, "ADMIN_URL_PREFIX", "admin/")
        self.prefix = "/" + str(prefix).strip("/") + "/"

    def __call__(self, request):
        if not request.path.startswith(self.prefix):
            return self.get_response(request)

        previous = translation.get_language()
        translation.activate(ADMIN_LANGUAGE)
        try:
            response = self.get_response(request)
        finally:
            # Язык — состояние потока, а поток переиспользуется под следующий
            # запрос. Не вернуть прежний — значит покрасить в русский и API,
            # которому не повезло попасть на тот же поток.
            translation.activate(previous) if previous else translation.deactivate()

        # Иначе кэши и прокси могут отдать русскую страницу тому, кто просил
        # другой язык (и наоборот).
        response.setdefault("Content-Language", ADMIN_LANGUAGE)
        return response
