"""MG_AIPING: спросить провайдера напрямую и увидеть отказ, а не догадываться.

Канонизация состава гасит ошибку пачки намеренно — из-за одного таймаута ронять
прогон на полутора тысячах рецептов незачем. Но пока она гасила молча, отличить
«модель не поняла ингредиент» от «до модели не достучались» по результату было
нельзя: прогон доходил до конца и выглядел успешным.

Здесь проверяется и прямая проверка связи, и то, что отказ провайдера при
канонизации виден в выводе.
"""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.recipes.management.commands.mg_ai_ping import mask


class TestMask:
    def test_середина_ключа_в_вывод_не_попадает(self):
        """Вывод уходит в переписку и в тикеты — целиком ключу там не место."""
        out = mask("sk-aitunnel-СЕКРЕТНАЯСЕРЕДИНА-1234")

        assert "СЕКРЕТНАЯСЕРЕДИНА" not in out

    def test_видно_чей_это_ключ(self):
        """Префикс не секрет и сразу отвечает, тот ли сервис: sk-aitunnel-, AQVN…"""
        assert "sk-aitunnel" in mask("sk-aitunnel-abcdefghij-1234")
        assert "sk-proj-" in mask("sk-proj-abcdefghijklmnop")

    def test_видно_какой_именно_ключ(self):
        """Хвост отличает новый ключ от старого, когда контейнер не перезапустили."""
        assert mask("sk-aitunnel-abcdefghij-1234").endswith("…1234, 27 символов)")

    def test_пустой_ключ_назван_прямо(self):
        assert mask("") == "не задан"

    def test_обрубок_назван_обрубком(self):
        """Ключ в пять символов — это ошибка при копировании, а не ключ."""
        assert "коротк" in mask("sk-12")


@pytest.mark.django_db
class TestPing:
    def test_живой_провайдер_показывает_ответ(self, capsys):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "Москва"
            call_command("mg_ai_ping")

        assert "Москва" in capsys.readouterr().out

    def test_отказ_это_ошибка_команды(self):
        """Молчаливый успех при лежащем провайдере — ровно то, от чего уходим."""
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("connection refused")

            with pytest.raises(CommandError, match="connection refused"):
                call_command("mg_ai_ping")

    def test_пустой_ответ_тоже_отказ(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "   "

            with pytest.raises(CommandError, match="пустой текст"):
                call_command("mg_ai_ping")

    def test_несобравшийся_клиент_это_ошибка(self):
        """Нет ключа или папки — падаем здесь, а не молча на середине импорта."""
        with patch("apps.common.ai_provider.get_ai_client", side_effect=RuntimeError("AI_API_KEY is not set")):
            with pytest.raises(CommandError, match="AI_API_KEY"):
                call_command("mg_ai_ping")


@pytest.mark.django_db
class TestCanonReportsFailures:
    def test_отказ_провайдера_попадает_в_лог(self):
        from apps.recipes.recipe_products import canonicalize_and_categorize

        lines = []
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("timeout")
            canonicalize_and_categorize(["гречка", "лук"], log=lines.append)

        assert any("ВНИМАНИЕ" in line and "timeout" in line for line in lines)
        assert any("без ответа — 2 из 2" in line for line in lines)

    def test_когда_всё_хорошо_предупреждения_нет(self):
        from apps.recipes.recipe_products import canonicalize_and_categorize

        lines = []
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = '[{"i": 0, "canon": "Гречка", "slug": "", "product": null}]'
            canonicalize_and_categorize(["гречка"], log=lines.append)

        assert not any("ВНИМАНИЕ" in line for line in lines)


@pytest.mark.django_db
class TestBothModelsChecked:
    """Модель канонизации ломается отдельно — проверять надо и её.

    Пользовательские пути (скан штрих-кода, фото, список покупок) живут на
    AI_TEXT_MODEL, долгий прогон по каталогу — на AI_CANON_MODEL. Зелёная
    проверка первой ничего не говорит про вторую: ровно так и вышло, когда
    ping отвечал «Москва» на gpt-4o-mini, а канонизация шла на другой модели.
    """

    def _cfg(self, **values):
        def fake(key, default=None, **kw):
            return values.get(key, default)

        return patch("decouple.config", side_effect=fake)

    def test_обе_модели_опрашиваются(self, capsys):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "Москва"
            with self._cfg(AI_TEXT_MODEL="gpt-4o-mini", AI_CANON_MODEL="gemini-3.7-flash"):
                call_command("mg_ai_ping")

        out = capsys.readouterr().out
        assert "AI_TEXT_MODEL — ответ" in out
        assert "AI_CANON_MODEL — ответ" in out

    def test_отказ_модели_канонизации_виден(self):
        answers = ["Москва", RuntimeError("HTTP 404 model not found")]

        def complete(*a, **kw):
            value = answers.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = complete
            with self._cfg(AI_TEXT_MODEL="gpt-4o-mini", AI_CANON_MODEL="gemini-3.7-flash"):
                with pytest.raises(CommandError, match="AI_CANON_MODEL"):
                    call_command("mg_ai_ping")

    def test_одинаковые_модели_не_спрашиваем_дважды(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "Москва"
            with self._cfg(AI_TEXT_MODEL="gpt-4o-mini", AI_CANON_MODEL="gpt-4o-mini"):
                call_command("mg_ai_ping")

        assert factory.return_value.complete.call_count == 1
