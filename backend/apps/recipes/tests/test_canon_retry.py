"""MG_AIRETRY: разовый сбой шлюза не должен стоить тридцати названий.

Канонизация шлёт названия пачками по тридцать. Шлюз срывается — за три прогона
подряд это были 504, 502 и таймаут, каждый раз на одной-двух пачках. Пачка при
сбое просто пропадала: повторный проход подбирал её один раз и тем же способом,
а если и он не проходил, тридцать названий оставались сырыми и связи по ним
цеплялись за старый мусор в каталоге.

Теперь та же пачка повторяется до трёх раз с нарастающей паузой: сбои у шлюза
короткие, и второй попытки обычно хватает.
"""

from unittest.mock import patch

import pytest

from apps.recipes.recipe_products import canonicalize_and_categorize

ANSWER = '[{"i": 0, "canon": "Гречка", "slug": "", "product": null}]'


@pytest.fixture(autouse=True)
def no_sleep():
    """Паузы между попытками в тестах не ждём."""
    with patch("apps.recipes.recipe_products.time.sleep"):
        yield


@pytest.mark.django_db
class TestRetry:
    def test_два_сбоя_подряд_пачку_не_теряют(self):
        """Раньше двух срывов хватало: один съедал основной проход, второй — повторный.

        Повторный проход — это ещё одна попытка, а не бесконечная: если и она
        не проходила, тридцать названий оставались сырыми.
        """
        answers = [RuntimeError("HTTP 502"), RuntimeError("HTTP 504"), ANSWER]

        def complete(*a, **kw):
            value = answers.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = complete
            out = canonicalize_and_categorize(["гречка"])

        assert out["гречка"][0] == "Гречка"

    def test_три_отказа_подряд_теряют_пачку(self):
        """Бесконечно долбиться в лежащий шлюз незачем — фиксируем и идём дальше."""
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 502")
            lines = []
            out = canonicalize_and_categorize(["гречка"], log=lines.append)

        assert out == {}
        assert factory.return_value.complete.call_count == 3 * 2  # основной проход + повторный
        assert any("пачка потеряна" in line for line in lines)

    def test_успешная_пачка_повторов_не_делает(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = ANSWER
            canonicalize_and_categorize(["гречка"])

        assert factory.return_value.complete.call_count == 1

    def test_в_логе_видно_попытки(self):
        answers = [RuntimeError("HTTP 502"), ANSWER]

        def complete(*a, **kw):
            value = answers.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = complete
            lines = []
            canonicalize_and_categorize(["гречка"], log=lines.append)

        assert any("попытка 1 не удалась" in line and "502" in line for line in lines)
        assert any("ок за" in line for line in lines)
