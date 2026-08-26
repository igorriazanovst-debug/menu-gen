"""MG_AIMODEL: отдельная модель под задачу.

Названия продуктов канонизирует ИИ, и результат его работы видит каждый
пользователь в каталоге холодильника и дневника. Дешёвая модель сбоит ровно
там, где больно: падежи («Йогурта», «Казеина»), слово-мера вместо продукта
(«Листочек Шалфея»), оборванная фраза. При этом канонизация запускается изредка
и пачками — переплата за запрос почти ничего не стоит, в отличие от разовых
запросов на пользовательских путях, где модель дёргают постоянно.

Поэтому модель выбирается на задачу: AI_CANON_MODEL для канонизации,
AI_IMAGE_PROMPT_MODEL для промптов картинок, AI_TEXT_MODEL для остального.
"""

from unittest.mock import patch

import pytest

from apps.common.ai_provider import get_ai_client


def env(**overrides):
    """Подменяет чтение настроек: ключи есть, остальное — значения по умолчанию."""
    base = {"AI_API_KEY": "sk-test-key", "AI_FOLDER_ID": "folder-1"}
    base.update(overrides)

    def fake_config(key, default=None, **kw):
        return base.get(key, default)

    return patch("apps.common.ai_provider.config", side_effect=fake_config)


class TestFactoryOverride:
    def test_модель_перебивается_параметром(self):
        with env():
            client = get_ai_client(provider="openai", model="deepseek-v4-pro")

        assert client._text_model == "deepseek-v4-pro"

    def test_перебивается_у_любого_провайдера(self):
        """Прошлая реализация работала только для Yandex и молчала на остальных."""
        for provider in ("openai", "yandex", "anthropic"):
            with env():
                client = get_ai_client(provider=provider, model="сильная-модель")

            assert client._text_model == "сильная-модель", provider

    def test_без_параметра_берётся_общая_настройка(self):
        with env(AI_TEXT_MODEL="gpt-4o-mini"):
            client = get_ai_client(provider="openai")

        assert client._text_model == "gpt-4o-mini"


@pytest.mark.django_db
class TestCanonModel:
    def test_канонизация_берёт_свою_модель(self):
        from apps.recipes.recipe_products import canonicalize_and_categorize

        def fake_config(key, default=None, **kw):
            return "сильная-модель" if key == "AI_CANON_MODEL" else default

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "[]"
            with patch("decouple.config", side_effect=fake_config):
                canonicalize_and_categorize(["гречка"])

        assert factory.call_args.kwargs["model"] == "сильная-модель"

    def test_без_настройки_модель_не_навязываем(self):
        from apps.recipes.recipe_products import canonicalize_and_categorize

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "[]"
            canonicalize_and_categorize(["гречка"])

        assert factory.call_args.kwargs["model"] is None


class TestSentenceCase:
    """MG_CANONCASE: каталог написан как «Лук репчатый», а не «Лук Репчатый».

    Модель охотно возвращает Title Case, и в подборщике две манеры письма рядом
    выглядят как две разные базы. Регистр — единственное в ответе модели, что
    можно поправить механически и наверняка.
    """

    def test_каждое_слово_с_заглавной_приводится_к_нашему_виду(self):
        from apps.recipes.recipe_products import _clean_canon

        assert _clean_canon("Сушеная Травка") == "Сушеная травка"
        assert _clean_canon("Рёбра Свинины") == "Рёбра свинины"

    def test_первая_буква_остаётся_заглавной(self):
        from apps.recipes.recipe_products import _clean_canon

        assert _clean_canon("гречка") == "Гречка"

    def test_мусорный_ответ_по_прежнему_none(self):
        from apps.recipes.recipe_products import _clean_canon

        assert _clean_canon("null") is None
        assert _clean_canon("  ") is None
