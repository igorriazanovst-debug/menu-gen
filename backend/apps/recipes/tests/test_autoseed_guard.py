"""MG_AUTOPROD2: в каталог не должно попадать то, что ИИ не разобрал.

Сборка связей рецепт→продукт заводит недостающий продукт сама. Название она
берёт у канонизатора — но канонизатор отвечает не всегда: на часть сегментов
состава он молчит оба прохода, и тогда подставлялось исходное написание из
рецепта. Так в общем каталоге, который пользователь видит в холодильнике и
дневнике, оказывались «Сливы», «Мандарина», «2 яйца вареных» и «Клюква для
украшения» — падежи, числительные и пояснения из текста рецепта.

Правило теперь такое: связь строим всегда (название и категория нужны списку
покупок), а новую запись в каталоге заводим только по разобранному сегменту.
"""

from unittest.mock import patch

import pytest

from apps.fridge.models import Product, ProductCategory
from apps.recipes.models import Recipe, RecipeProduct
from apps.recipes.recipe_products import canonicalize_and_categorize, rebuild_recipe_links


@pytest.fixture
def categories(db):
    ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее", "is_active": True})
    cat, _ = ProductCategory.objects.get_or_create(slug="fruit", defaults={"name_ru": "Фрукты", "is_active": True})
    return cat


@pytest.fixture
def recipe(db):
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
        return Recipe.objects.create(
            title="Компот",
            ingredients=[{"name": "сливы", "quantity": "300", "unit": "г", "grams": 300}],
        )


def build(recipe, canon_map):
    return rebuild_recipe_links(recipe, canon_map=canon_map, force=True, create_missing=True)


@pytest.mark.django_db
class TestSeedOnlyRecognized:
    def test_молчание_канонизатора_не_создаёт_продукт(self, recipe, categories):
        """Пустой словарь — ИИ не ответил ни за один из двух проходов."""
        build(recipe, canon_map={})

        assert not Product.objects.filter(source=Product.Source.AUTO).exists()

    def test_связь_при_этом_строится(self, recipe, categories):
        """Название и категория нужны рубрикатору списка покупок."""
        build(recipe, canon_map={})

        link = RecipeProduct.objects.get(recipe=recipe)
        assert link.name_canonical == "Сливы"
        assert link.product_id is None

    def test_разобранный_сегмент_продукт_создаёт(self, recipe, categories):
        """Ради этого авто-создание и заведено: иначе рецепт не найдётся."""
        build(recipe, canon_map={"сливы": ("Слива", "fruit", None)})

        created = Product.objects.get(source=Product.Source.AUTO)
        assert created.name == "Слива"
        assert created.category_fk.slug == "fruit"


@pytest.mark.django_db
class TestCanonMapMarksFailures:
    def test_неотвеченный_сегмент_в_словарь_не_попадает(self):
        """Раньше на его месте была заглушка, и «ИИ молчал» выглядело ответом."""
        with patch("apps.common.ai_provider.get_ai_client", side_effect=RuntimeError("нет ключа")):
            out = canonicalize_and_categorize(["сливы", "мандарина"])

        assert out == {}

    def test_явный_отказ_ии_это_ответ(self):
        """None от ИИ означает «это не продукт» — такой сегмент в словаре есть."""
        with patch("apps.common.ai_provider.get_ai_client") as client:
            client.return_value.complete.return_value = '[{"i": 0, "canon": null, "slug": "", "product": null}]'
            out = canonicalize_and_categorize(["по вкусу"])

        assert "по вкусу" in out
        assert out["по вкусу"][0] is None
