"""MG_MAILAPI: определение настроенности отправки почты по бэкенду."""

from apps.common.mail import email_enabled


class TestEmailEnabled:
    def test_smtp_without_host_disabled(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = ""
        assert email_enabled() is False

    def test_smtp_with_host_enabled(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "smtp.yandex.ru"
        assert email_enabled() is True

    def test_proxy_backend_treated_as_smtp(self, settings):
        """Наш ProxyEmailBackend — подкласс SMTP, значит EMAIL_HOST обязателен."""
        settings.EMAIL_BACKEND = "apps.common.email_backend.ProxyEmailBackend"
        settings.EMAIL_HOST = ""
        assert email_enabled() is False
        settings.EMAIL_HOST = "smtp.yandex.ru"
        assert email_enabled() is True

    def test_http_api_backend_enabled_without_smtp_host(self, settings):
        """Anymail (HTTP API) не нуждается в EMAIL_HOST — отправка доступна."""
        settings.EMAIL_BACKEND = "anymail.backends.unisender_go.EmailBackend"
        settings.EMAIL_HOST = ""
        settings.ANYMAIL = {
            "UNISENDER_GO_API_KEY": "test-key",
            "UNISENDER_GO_API_URL": "https://go1.unisender.ru/ru/transactional/api/v1",
        }
        assert email_enabled() is True

    def test_locmem_backend_enabled(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        settings.EMAIL_HOST = ""
        assert email_enabled() is True
