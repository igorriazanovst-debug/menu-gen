"""MG_AIBATCH: пакетная работа с ИИ — таймаут, повтор и честный итог.

На проде `dedup_products_ai` отвалился на пяти пачках из десяти:

    Read timed out. (read timeout=30.0)
    SSL: UNEXPECTED_EOF_WHILE_READING

Причин было две, и обе в коде, а не в сети. Команда звала get_ai_client() без
таймаута — то есть 30 секунд, подобранных под разовый запрос в пользовательском
пути, — и просила при этом до 3000 токенов ответа на пачку. И она же не
повторяла попытку: обрыв TLS держится секунды и проходит сам, а пачка терялась
целиком.

Хуже самих отказов было третье: команда напечатала «Групп со слиянием: 1». Это
читается как «дублей почти нет», хотя половина названий до модели не доехала.
"""

from unittest import mock

import pytest

from apps.common.ai_provider import AIConfigError, AIRequestError, complete_with_retry, get_batch_ai_client


class FlakyClient:
    """Отдаёт ошибку связи заданное число раз, потом отвечает."""

    def __init__(self, failures, answer="готово"):
        self.failures = failures
        self.answer = answer
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise AIRequestError("OpenAI request failed: Read timed out. (read timeout=30.0)")
        return self.answer


class TestПовтор:
    def test_обрыв_связи_переживается(self):
        client = FlakyClient(failures=2)

        out = complete_with_retry(client, attempts=3, pause=0, prompt="[]", system="s")

        assert out == "готово"
        assert client.calls == 3

    def test_попытки_не_бесконечны(self):
        client = FlakyClient(failures=99)

        with pytest.raises(AIRequestError):
            complete_with_retry(client, attempts=3, pause=0, prompt="[]", system="s")

        assert client.calls == 3

    def test_с_первого_раза_не_повторяем(self):
        client = FlakyClient(failures=0)

        complete_with_retry(client, attempts=3, pause=0, prompt="[]", system="s")

        assert client.calls == 1

    def test_ошибку_настройки_не_повторяем(self):
        """Неверный ключ не пройдёт и на третий раз — ждать незачем."""

        class Broken:
            calls = 0

            def complete(self, **kwargs):
                Broken.calls += 1
                raise AIConfigError("AI_API_KEY пуст")

        with pytest.raises(AIConfigError):
            complete_with_retry(Broken(), attempts=3, pause=0, prompt="[]")

        assert Broken.calls == 1


class TestПакетныйКлиент:
    def test_берёт_таймаут_канонизации_а_не_пользовательский(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        monkeypatch.setenv("AI_TIMEOUT", "30")
        monkeypatch.setenv("AI_CANON_TIMEOUT", "120")

        with mock.patch("apps.common.ai_provider.OpenAIAIClient") as made:
            get_batch_ai_client()

        assert made.call_args.kwargs["timeout"] == 120

    def test_явный_таймаут_сильнее_настроек(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        monkeypatch.setenv("AI_CANON_TIMEOUT", "120")

        with mock.patch("apps.common.ai_provider.OpenAIAIClient") as made:
            get_batch_ai_client(timeout=300)

        assert made.call_args.kwargs["timeout"] == 300


class TestПроверкаДоступности:
    """Клиент и проверка доступности должны ходить одинаково.

    Они разъехались: клиент перевели на пакетный таймаут, а check_ai_available()
    рядом оставили голой. Команда падала на проверке, не начав работу:
    «ИИ-провайдер недоступен: Read timed out. (read timeout=30.0)» — при том,
    что сама работа пошла бы со 120 секундами.
    """

    def test_проверка_идёт_теми_же_настройками_что_и_работа(self, monkeypatch):
        from apps.common.ai_provider import batch_ai_settings, check_batch_ai_available

        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        monkeypatch.setenv("AI_TIMEOUT", "30")
        monkeypatch.setenv("AI_CANON_TIMEOUT", "120")
        monkeypatch.setenv("AI_CANON_MODEL", "gemini-3.7-flash")

        with mock.patch("apps.common.ai_provider.check_ai_available") as checked:
            check_batch_ai_available()

        passed = dict(checked.call_args.kwargs)
        # attempts и log — про повторы и про вывод, а не про то, чем ходить в
        # модель: сверяем отдельно, иначе проверка ловила бы каждое новое поле.
        assert passed.pop("attempts") == 3
        passed.pop("log", None)
        assert passed == batch_ai_settings()
        assert passed["timeout"] == 120
        assert passed["model"] == "gemini-3.7-flash"


class TestПроверкаПовторяется:
    """MG_AIPROBE: разовый обрыв TLS не означает, что провайдер лежит.

    На dev команда не начиналась вовсе: «ИИ-провайдер недоступен: SSL:
    UNEXPECTED_EOF_WHILE_READING». Повтор к рабочим пачкам был приделан, а
    проверка ходила одним запросом — и одна сорвавшаяся попытка отменяла
    часовую работу, которую сами обрывы не остановили бы.
    """

    def test_перед_пакетной_работой_проверка_повторяется(self, monkeypatch):
        from apps.common.ai_provider import check_batch_ai_available

        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        client = FlakyClient(failures=2, answer="Москва")

        with mock.patch("apps.common.ai_provider.get_ai_client", return_value=client):
            check_batch_ai_available(attempts=3)

        assert client.calls == 3

    def test_в_пользовательском_пути_проверка_одна(self, monkeypatch):
        """Там ждать нельзя: человек смотрит на экран."""
        from apps.common.ai_provider import AIUnavailable, check_ai_available

        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        client = FlakyClient(failures=1, answer="Москва")

        with mock.patch("apps.common.ai_provider.get_ai_client", return_value=client):
            with pytest.raises(AIUnavailable):
                check_ai_available()

        assert client.calls == 1

    def test_мёртвый_провайдер_всё_равно_признаётся_мёртвым(self, monkeypatch):
        from apps.common.ai_provider import AIUnavailable, check_batch_ai_available

        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "test-key")
        client = FlakyClient(failures=99)

        with mock.patch("apps.common.ai_provider.get_ai_client", return_value=client):
            with pytest.raises(AIUnavailable):
                check_batch_ai_available(attempts=3)

        assert client.calls == 3
