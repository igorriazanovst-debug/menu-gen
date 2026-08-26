"""MG_CANONCACHE: ответы модели переживают обрыв прогона.

Проход ИИ идёт целиком до того, как записана хоть одна связь. За один день так
пропало три прогона по 59 пачек: падение на MultipleObjectsReturned, смена
модели и обрыв терминала — каждый раз вместе со временем и деньгами.

Кэш решает это, но у него есть цена: старый ответ может пережить правку
промпта и молча испортить результат. Поэтому он привязан к модели и к тексту
промпта — и это здесь главное, что проверяется.
"""

import json
from unittest.mock import patch

import pytest

from apps.recipes.recipe_products import canonicalize_and_categorize

ANSWER = '[{"i": 0, "canon": "Гречка", "slug": "", "product": null}]'


@pytest.fixture
def cache_file(tmp_path):
    return str(tmp_path / "canon_cache.json")


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("apps.recipes.recipe_products.time.sleep"):
        yield


def run(names, cache_file, answer=ANSWER):
    with patch("apps.common.ai_provider.get_ai_client") as factory:
        factory.return_value.complete.return_value = answer
        out = canonicalize_and_categorize(names, cache_path=cache_file)
        return out, factory.return_value.complete.call_count


@pytest.mark.django_db
class TestCache:
    def test_второй_прогон_модель_не_дёргает(self, cache_file):
        run(["гречка"], cache_file)

        out, calls = run(["гречка"], cache_file)

        assert calls == 0
        assert out["гречка"][0] == "Гречка"

    def test_спрашиваем_только_новое(self, cache_file):
        run(["гречка"], cache_file)

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            # Индекс в ответе должен совпадать с тем, что ушёл в запросе:
            # модель отвечает на позиции, а не на порядок в пачке.
            factory.return_value.complete.return_value = '[{"i": 1, "canon": "Лук", "slug": "", "product": null}]'
            out = canonicalize_and_categorize(["гречка", "лук"], cache_path=cache_file)
            sent = factory.return_value.complete.call_args.kwargs["prompt"]

        assert "лук" in sent and "гречка" not in sent
        assert out["гречка"][0] == "Гречка" and out["лук"][0] == "Лук"

    def test_кэш_пишется_после_каждой_пачки(self, cache_file):
        """Обрыв на середине прохода не должен стоить уже оплаченного.

        Первая пачка проходит, вторая срывается насмерть — в файле обязана
        остаться первая. Прогон при этом не падает: сбой пачки гасится, чтобы
        одна неудача не роняла работу на двух тысячах рецептов.
        """
        calls = {"n": 0}

        def complete(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return ANSWER
            raise RuntimeError("обрыв")

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = complete
            out = canonicalize_and_categorize(["гречка", "лук"], chunk_size=1, cache_path=cache_file)

        assert "лук" not in out
        with open(cache_file, encoding="utf-8") as fh:
            saved = json.load(fh)
        assert "гречка" in saved["items"]

    def test_смена_модели_обесценивает_кэш(self, cache_file):
        run(["гречка"], cache_file)

        def other_model(key, default=None, **kw):
            return "другая-модель" if key == "AI_CANON_MODEL" else default

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = ANSWER
            with patch("decouple.config", side_effect=other_model):
                canonicalize_and_categorize(["гречка"], cache_path=cache_file)

            assert factory.return_value.complete.call_count == 1

    def test_правка_промпта_обесценивает_кэш(self, cache_file):
        """Иначе улучшения промпта молча не применялись бы к разобранным названиям."""
        run(["гречка"], cache_file)

        with patch("apps.recipes.recipe_products._SYS_CANON_CAT", "другой промпт __PRODUCTS__ __LISTING__"):
            _out, calls = run(["гречка"], cache_file)

        assert calls == 1

    def test_битый_файл_прогону_не_мешает(self, cache_file):
        with open(cache_file, "w", encoding="utf-8") as fh:
            fh.write("{это не json")

        out, calls = run(["гречка"], cache_file)

        assert calls == 1
        assert out["гречка"][0] == "Гречка"

    def test_без_кэша_работаем_как_раньше(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = ANSWER
            out = canonicalize_and_categorize(["гречка"], cache_path=None)

        assert out["гречка"][0] == "Гречка"
