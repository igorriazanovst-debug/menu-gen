from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.users",
    "apps.recipes",
    "apps.family",
    "apps.fridge",
    "apps.menu",
    "apps.diary",
    "apps.shopping",
    "apps.specialists",
    "apps.subscriptions",
    "apps.payments",
    "apps.notifications",
    "apps.social",
    "apps.sync",
    "apps.legal",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # RA-001
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "options": "-c search_path=public",
        },
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 5},
    },  # MG_208_V_be_settings
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "users.User"

LANGUAGE_CODE = "ru-ru"
# ── RA-001 i18n (admin RU/EN, extensible) ─────────────────────────
from django.utils.translation import gettext_lazy as _ra_  # noqa: E402

LANGUAGES = [
    ("ru", _ra_("Russian")),
    ("en", _ra_("English")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

# MG_OFFIMG: источник фото продуктов.
#   wikimedia (по умолчанию) — Wikimedia Commons по англ. названию (перевод
#     RU→EN через AI), фолбэк Openverse. Достижим с серверов, где Pixabay блокируется.
#   pixabay — качественный сток (category=food), но требует ключ И сетевой доступ
#     к pixabay.com (на части серверов заблокирован).
PRODUCT_IMAGE_SOURCE = config("PRODUCT_IMAGE_SOURCE", default="wikimedia")

# MG_PAYSTUB: тестовый режим оплаты. True — вместо реальной ЮKassa используется
# заглушка с полной имитацией флоу (создание платежа → страница оплаты → вебхук
# payment.succeeded → назначение тарифа). В проде: False + реальные YOOKASSA_*.
PAYMENTS_STUB = config("PAYMENTS_STUB", default=True, cast=bool)

# MG_EMAILVERIFY: базовый URL веб-приложения для ссылок из писем (подтверждение
# e-mail и т.п.). Прод: https://menugen.ru; dev: http://<host>:8081. Если пусто —
# фолбэк на BACKEND_PUBLIC_URL, затем на https://menugen.ru.
FRONTEND_URL = config("FRONTEND_URL", default="")

# MG_PHONEVERIFY: подтверждение телефона через бот мессенджера.
# Telegram: токен и username бота от @BotFather. Webhook-секрет сверяется с
# заголовком X-Telegram-Bot-Api-Secret-Token (прод). В dev используется
# long-polling (management-команда run_telegram_bot), webhook не нужен.
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = config("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = config("TELEGRAM_WEBHOOK_SECRET", default="")
# Прокси для запросов к api.telegram.org (в РФ часто заблокирован). Напр.
# socks5h://xray:1080 — локальный SOCKS5 от Xray-клиента (VLESS/Reality).
# Пусто — ходим напрямую. Для socks5 нужен пакет PySocks (в requirements).
TELEGRAM_PROXY = config("TELEGRAM_PROXY", default="")
# Max (max.ru): токен и username бота из кабинета разработчика (dev.max.ru).
MAX_BOT_TOKEN = config("MAX_BOT_TOKEN", default="")
MAX_BOT_USERNAME = config("MAX_BOT_USERNAME", default="")
# База Bot API Max (на случай смены домена платформой).
MAX_API_BASE = config("MAX_API_BASE", default="https://platform-api2.max.ru")
# У Max нет заголовка с секретом — секрет передаётся сегментом URL webhook:
# .../api/v1/auth/max/webhook/<MAX_WEBHOOK_SECRET>/
MAX_WEBHOOK_SECRET = config("MAX_WEBHOOK_SECRET", default="")

PIXABAY_API_KEY = config("PIXABAY_API_KEY", default="")
PIXABAY_LANG = config("PIXABAY_LANG", default="ru")

# MG_SHOPIMG: изображения товаров приходят как base64 в JSON-теле — поднимаем
# лимит тела запроса (дефолт Django 2.5 МБ мал для фото). Фронт дополнительно
# сжимает картинку до ~сотен КБ, но держим запас.
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "100/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=30, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MenuGen API",
    "DESCRIPTION": "API для приложения Генератор меню",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

_cors_origins = config("CORS_ALLOWED_ORIGINS", default="")
CORS_ALLOWED_ORIGINS = [o for o in _cors_origins.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# ── HTTPS / reverse-proxy hardening (env-driven, no-op by default) ────────────
# Всё ниже включается только через .env, поэтому на текущем (HTTP) сервере
# поведение не меняется. На новом сервере (nginx + Let's Encrypt, один домен)
# выставляем эти переменные, чтобы админка/CSRF/куки корректно работали за
# TLS-прокси.
#
# CSRF_TRUSTED_ORIGINS — список origin'ов со схемой (напр. https://menugen.ru).
# Нужен для формы логина в /admin/ и любых POST с session-аутентификацией.
_csrf_origins = config("CSRF_TRUSTED_ORIGINS", default="")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]

# Django должен доверять заголовку X-Forwarded-Proto от nginx, иначе request.is_secure()
# всегда False за прокси и редиректы/куки ломаются. Включаем только когда прокси его
# действительно проставляет.
if config("USE_X_FORWARDED_PROTO", default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

USE_X_FORWARDED_HOST = config("USE_X_FORWARDED_HOST", default=False, cast=bool)

# Secure-куки и HSTS — включаем на HTTPS-сервере.
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)

CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Moscow"

# MG_MAILPROXY: на российском хостинге исходящие SMTP-порты часто закрыты
# ([Errno 101] Network is unreachable). Бэкенд ProxyEmailBackend умеет ходить
# через SOCKS5 (тот же Xray, что и Telegram-бот) — см. EMAIL_PROXY ниже.
# Пустой EMAIL_PROXY = прямое соединение (штатное поведение Django).
EMAIL_BACKEND = config("EMAIL_BACKEND", default="apps.common.email_backend.ProxyEmailBackend")
EMAIL_PROXY = config("EMAIL_PROXY", default="")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
# STARTTLS (порт 587) vs SSL (порт 465) — взаимоисключающие. По умолчанию STARTTLS.
# Для Яндекса рекомендуется SSL: EMAIL_PORT=465, EMAIL_USE_SSL=True, EMAIL_USE_TLS=False.
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
# Без таймаута заблокированный SMTP-порт вешает запрос/команду до бесконечности.
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=20, cast=int)

# MG_MAILAPI: отправка писем через HTTP API провайдера (порт 443) — единственный
# рабочий вариант, когда хостинг и VPS режут исходящие SMTP-порты. Используется
# django-anymail: выбор ESP делается через EMAIL_BACKEND в .env, например
#   EMAIL_BACKEND=anymail.backends.unisender_go.EmailBackend
# (аналогично доступны mailgun, resend, brevo, sendgrid и др. — см. Anymail).
# Ключи ниже пустые, пока провайдер не подключён; Anymail читает их из ANYMAIL.
ANYMAIL = {
    # Unisender Go: URL зависит от дата-центра аккаунта (go1/go2 — см. кабинет).
    "UNISENDER_GO_API_KEY": config("UNISENDER_GO_API_KEY", default=""),
    "UNISENDER_GO_API_URL": config(
        "UNISENDER_GO_API_URL",
        default="https://go1.unisender.ru/ru/transactional/api/v1",
    ),
    # На случай смены провайдера — ключи подхватятся без правок кода.
    "MAILGUN_API_KEY": config("MAILGUN_API_KEY", default=""),
    "RESEND_API_KEY": config("RESEND_API_KEY", default=""),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Celery Beat Schedule ───────────────────────────────────────────────────────

CELERY_BEAT_SCHEDULE = {
    "check-fridge-expiry": {
        "task": "apps.notifications.tasks.check_fridge_expiry",
        "schedule": crontab(hour=9, minute=0),  # ежедневно в 09:00
    },
    "expire-subscriptions": {
        "task": "apps.notifications.tasks.expire_subscriptions",
        "schedule": crontab(hour=0, minute=5),  # ежедневно в 00:05
    },
    "send-menu-reminder": {
        "task": "apps.notifications.tasks.send_menu_reminder",
        "schedule": crontab(day_of_week=1, hour=10, minute=0),  # каждый понедельник в 10:00
    },
    # MG_608_V_beat: ежедневная очистка карантина меню (purge_after < now)
    "purge-expired-menus": {
        "task": "apps.menu.tasks.purge_expired_menus",
        "schedule": crontab(hour=3, minute=15),
    },
}

# drf-spectacular enum overrides
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"] = {
    "SubscriptionStatusEnum": "apps.subscriptions.models.Subscription.Status",
    "PaymentStatusEnum": "apps.payments.models.Payment.Status",
    "MenuStatusEnum": "apps.menu.models.Menu.Status",
}


# ── Fridge: OpenFoodFacts fallback for unknown barcodes ──────────────
OPENFOODFACTS_BASE_URL = config(
    "OPENFOODFACTS_BASE_URL",
    default="https://world.openfoodfacts.org",
)
OPENFOODFACTS_TIMEOUT = config("OPENFOODFACTS_TIMEOUT", default=4.0, cast=float)
OPENFOODFACTS_USER_AGENT = config(
    "OPENFOODFACTS_USER_AGENT",
    default="MenuGen/1.0 (+https://menugen.local)",
)


# ── AI provider (provider-agnostic; Yandex Cloud / Anthropic) ────────
AI_PROVIDER = config("AI_PROVIDER", default="yandex")
AI_BASE_URL = config("AI_BASE_URL", default="https://llm.api.cloud.yandex.net/v1")
AI_API_KEY = config("AI_API_KEY", default="")
AI_FOLDER_ID = config("AI_FOLDER_ID", default="")
AI_TEXT_MODEL = config("AI_TEXT_MODEL", default="yandexgpt-lite")
AI_TEXT_MODEL_PRO = config("AI_TEXT_MODEL_PRO", default="yandexgpt")
AI_TIMEOUT = config("AI_TIMEOUT", default=30.0, cast=float)

# ─── Photo recognition (Vision OCR + LLM extraction) ────────────────────────
# OCR endpoint is derived from AI_BASE_URL domain unless OCR_BASE_URL is set.
OCR_BASE_URL = config("OCR_BASE_URL", default="")
OCR_MODEL = config("OCR_MODEL", default="page")
OCR_MAX_IMAGE_MB = config("OCR_MAX_IMAGE_MB", default=10, cast=float)
# Comma-separated language codes for OCR (e.g. "ru,en").
OCR_LANGUAGE_CODES = [c.strip() for c in config("OCR_LANGUAGE_CODES", default="ru,en").split(",") if c.strip()]
# Model used to extract product name from noisy OCR text.
# Defaults to AI_TEXT_MODEL (yandexgpt-lite) per decision; override via env.
AI_VISION_EXTRACT_MODEL = config("AI_VISION_EXTRACT_MODEL", default=AI_TEXT_MODEL)

# ─── Image generation (YandexART) ───────────────────────────────────────────
# Async foundation-models image generation. Host is derived from AI_BASE_URL's
# root (…/v1 stripped) unless AI_IMAGE_BASE_URL overrides it. Same Api-Key and
# folder as the text/OCR clients. Model defaults to "yandex-art".
AI_IMAGE_BASE_URL = config("AI_IMAGE_BASE_URL", default="")
AI_IMAGE_MODEL = config("AI_IMAGE_MODEL", default="yandex-art")
# YandexART runs under a dedicated service account ("menugen-image"). Its own
# Api-Key (and folder, if different) — fall back to the shared text creds.
AI_IMAGE_API_KEY = config("AI_IMAGE_API_KEY", default="")
AI_IMAGE_FOLDER_ID = config("AI_IMAGE_FOLDER_ID", default="")
AI_IMAGE_TIMEOUT = config("AI_IMAGE_TIMEOUT", default=30.0, cast=float)
# Seconds to wait for the async generation operation to finish (poll loop).
AI_IMAGE_POLL_TIMEOUT = config("AI_IMAGE_POLL_TIMEOUT", default=120.0, cast=float)
AI_IMAGE_POLL_INTERVAL = config("AI_IMAGE_POLL_INTERVAL", default=2.0, cast=float)
# Prompt-builder text model (recipe -> visual slots). Defaults to the PRO model
# for richer descriptions; override via env.
AI_IMAGE_PROMPT_MODEL = config("AI_IMAGE_PROMPT_MODEL", default=AI_TEXT_MODEL_PRO)
