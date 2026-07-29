"""MG_MAILPROXY: SMTP-бэкенд, умеющий ходить через SOCKS5-прокси.

Зачем: на российском хостинге исходящие SMTP-порты (465/587) часто закрыты —
соединение с smtp.yandex.ru падает с ``[Errno 101] Network is unreachable``.
Тот же прокси (Xray-клиент с VLESS/Reality), через который работает Telegram-бот,
пускаем и для почты.

Включение (.env):
    EMAIL_BACKEND=apps.common.email_backend.ProxyEmailBackend
    EMAIL_PROXY=socks5h://xray:1080

Если ``EMAIL_PROXY`` пуст — бэкенд ведёт себя как штатный Django SMTP-бэкенд
(прямое соединение), поэтому его можно оставить включённым всегда.
Схема ``socks5h`` резолвит DNS на стороне прокси (важно при блокировках),
``socks5`` — локально.
"""

from __future__ import annotations

import smtplib
from urllib.parse import urlparse

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSmtpEmailBackend


def _proxy_url() -> str:
    return getattr(settings, "EMAIL_PROXY", "") or ""


def _socks_connect(host, port, timeout):
    """Открывает TCP-соединение до (host, port) через SOCKS5 из EMAIL_PROXY."""
    parsed = urlparse(_proxy_url())
    scheme = (parsed.scheme or "socks5").lower()
    if scheme not in ("socks5", "socks5h", "socks4", "socks4a"):
        raise ValueError(f"EMAIL_PROXY: неподдерживаемая схема {scheme!r} (нужен socks5/socks5h)")

    import socks  # PySocks

    proxy_type = socks.SOCKS4 if scheme.startswith("socks4") else socks.SOCKS5
    # socks5h / socks4a — резолвить имя на стороне прокси.
    rdns = scheme.endswith("h") or scheme.endswith("a")

    sock = socks.socksocket()
    sock.set_proxy(
        proxy_type,
        parsed.hostname,
        parsed.port or 1080,
        rdns=rdns,
        username=parsed.username or None,
        password=parsed.password or None,
    )
    if timeout is not None:
        sock.settimeout(timeout)
    sock.connect((host, port))
    return sock


class ProxySMTP(smtplib.SMTP):
    """SMTP (STARTTLS / без шифрования) через SOCKS5."""

    def _get_socket(self, host, port, timeout):
        return _socks_connect(host, port, timeout)


class ProxySMTP_SSL(smtplib.SMTP_SSL):  # noqa: N801 — имя в стиле smtplib
    """SMTP поверх SSL (порт 465) через SOCKS5."""

    def _get_socket(self, host, port, timeout):
        sock = _socks_connect(host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=self._host)


class ProxyEmailBackend(DjangoSmtpEmailBackend):
    """Django SMTP-бэкенд: через SOCKS5, если задан EMAIL_PROXY, иначе напрямую."""

    @property
    def connection_class(self):
        if not _proxy_url():
            # Прокси не настроен — штатное поведение Django.
            return smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        return ProxySMTP_SSL if self.use_ssl else ProxySMTP
