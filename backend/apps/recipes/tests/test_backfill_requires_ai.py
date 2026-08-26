"""MG_AIPING: сборка связей не идёт при мёртвом провайдере.

Канонизация гасит ошибку каждой пачки, чтобы один таймаут не ронял проход по
двум тысячам рецептов. Но если провайдер не отвечает вообще — недействительный
ключ, кончилась квота, — гасить нечего: не отвечает ни одна пачка, и прогон
доходит до конца, выглядя успешным.

Связи при этом строятся по сырым названиям прямо из текста рецепта, в падежах и
с числительными («сливы», «2 яйца вареных», «клюква для украшения»). Раньше по
ним ещё и заводились продукты в общем каталоге — так туда попали «Мандарина» и
«Время приготовления 40 мин».

Поэтому перед долгим прогоном — один дешёвый запрос, и отказ прекращает работу.
"""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.recipes.models import Recipe, RecipeProduct
from apps.common.ai_provider import AIUnavailable, check_ai_available


@pytest.fixture
def recipe(db):
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
        return Recipe.objects.create(title="Компот", ingredients=[{"name": "сливы", "grams": 300}])


@pytest.mark.django_db
class TestCheck:
    def test_отказ_провайдера_это_исключение(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            with pytest.raises(AIUnavailable, match="HTTP 401"):
                check_ai_available()

    def test_пустой_ответ_тоже_отказ(self):
        """Провайдер, который отвечает пустотой, для канонизации так же бесполезен."""
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = ""

            with pytest.raises(AIUnavailable):
                check_ai_available()

    def test_живой_провайдер_проходит_молча(self):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.return_value = "Москва"

            assert check_ai_available() is None


@pytest.mark.django_db
class TestBackfillCommand:
    def test_команда_падает_и_объясняет(self, recipe):
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            with pytest.raises(CommandError, match="mg_ai_ping"):
                call_command("mg_backfill_recipe_products")

    def test_связи_при_этом_не_строятся(self, recipe):
        """Мусорные связи хуже отсутствующих: их потом не отличить от настоящих."""
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            with pytest.raises(CommandError):
                call_command("mg_backfill_recipe_products")

        assert RecipeProduct.objects.count() == 0

    def test_no_ai_разрешает_осознанный_прогон(self, recipe):
        """Иногда связи по названиям нужнее, чем никакие, — но только явно."""
        with patch("apps.common.ai_provider.get_ai_client") as factory:
            factory.return_value.complete.side_effect = RuntimeError("HTTP 401")

            call_command("mg_backfill_recipe_products", "--no-ai")

        assert RecipeProduct.objects.filter(recipe=recipe).exists()
