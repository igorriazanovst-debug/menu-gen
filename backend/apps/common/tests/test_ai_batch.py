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
