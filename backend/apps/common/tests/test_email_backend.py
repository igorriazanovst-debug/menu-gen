"""MG_MAILPROXY: тесты SMTP-бэкенда с поддержкой SOCKS5-прокси.

Сеть не задействуется: проверяем выбор класса соединения и параметры прокси.
"""

import smtplib

import pytest

from apps.common.email_backend import ProxyEmailBackend, ProxySMTP, ProxySMTP_SSL, _socks_connect


class TestConnectionClass:
    def test_direct_when_no_proxy(self, settings):
        settings.EMAIL_PROXY = ""
        # use_tls/use_ssl взаимоисключающие — задаём пару явно.
        assert ProxyEmailBackend(use_ssl=False, use_tls=True).connection_class is smtplib.SMTP
        assert ProxyEmailBackend(use_ssl=True, use_tls=False).connection_class is smtplib.SMTP_SSL

    def test_proxy_classes_when_configured(self, settings):
        settings.EMAIL_PROXY = "socks5h://xray:1080"
        assert ProxyEmailBackend(use_ssl=False, use_tls=True).connection_class is ProxySMTP
        assert ProxyEmailBackend(use_ssl=True, use_tls=False).connection_class is ProxySMTP_SSL


class TestSocksConnect:
    def test_rejects_unknown_scheme(self, settings):
        settings.EMAIL_PROXY = "http://proxy:3128"
        with pytest.raises(ValueError, match="неподдерживаемая схема"):
            _socks_connect("smtp.yandex.ru", 465, 5)

    def test_sets_proxy_params(self, settings, monkeypatch):
        """socks5h → rdns=True, host/port из URL, соединение к целевому серверу."""
        settings.EMAIL_PROXY = "socks5h://xray:1080"
        calls = {}

        class FakeSocket:
            def set_proxy(self, ptype, host, port, rdns=False, username=None, password=None):
                calls["proxy"] = (ptype, host, port, rdns, username, password)

            def settimeout(self, t):
                calls["timeout"] = t

            def connect(self, addr):
                calls["connect"] = addr

        import socks

        monkeypatch.setattr(socks, "socksocket", FakeSocket)
        _socks_connect("smtp.yandex.ru", 465, 7)

        ptype, host, port, rdns, user, pwd = calls["proxy"]
        assert ptype == socks.SOCKS5
        assert (host, port) == ("xray", 1080)
        assert rdns is True  # socks5h — DNS резолвит прокси
        assert (user, pwd) == (None, None)
        assert calls["connect"] == ("smtp.yandex.ru", 465)
        assert calls["timeout"] == 7

    def test_socks5_without_h_resolves_locally(self, settings, monkeypatch):
        settings.EMAIL_PROXY = "socks5://xray:1080"
        calls = {}

        class FakeSocket:
            def set_proxy(self, ptype, host, port, rdns=False, username=None, password=None):
                calls["rdns"] = rdns

            def settimeout(self, t):
                pass

            def connect(self, addr):
                pass

        import socks

        monkeypatch.setattr(socks, "socksocket", FakeSocket)
        _socks_connect("smtp.yandex.ru", 465, 5)
        assert calls["rdns"] is False
