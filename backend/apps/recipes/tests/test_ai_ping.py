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
    def test_ключ_в_вывод_не_попадает(self):
        """Вывод команды уходит в переписку и в тикеты — целиком ключу там не место."""
        out = mask("AQVN0secretkey1234")

        assert "secretkey" not in out
        assert out.endswith("…1234)")

    def test_пустой_ключ_назван_прямо(self):
        assert mask("") == "не задан"


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

            with pytest.raises(CommandError, match="пустым"):
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
