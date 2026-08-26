"""MG_AUTOPROD2: разбор того, что машина уже насыпала в каталог.

Записи `source=auto` заводит сборка связей рецепт→продукт, и в подборщиках они
видны наравне с выверенными. За несколько импортов туда натекло то, что едой не
является: разметка страницы рецепта («Время приготовления 40 мин», «Итальянская
кухня») и названия блюд, стоявшие в исходнике в списке ингредиентов.

Первая версия команды сносила всё машинное из «Прочего» — и забирала вместе с
мусором «Бекон копчёный» и «Соль мелкую». Поэтому проверять здесь надо не
«удалилось ли», а границы: что считается мусором и чего команда не трогает.
"""

import pytest
from django.core.management import call_command

from apps.fridge.management.commands.mg_prune_auto_products import is_metadata
from apps.fridge.models import Product, ProductAlias, ProductCategory
from apps.recipes.models import Recipe, RecipeProduct


@pytest.fixture
def cats(db):
    other, _ = ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее", "is_active": True})
    fruit, _ = ProductCategory.objects.get_or_create(slug="fruit", defaults={"name_ru": "Фрукты", "is_active": True})
    return other, fruit


@pytest.fixture
def auto(cats):
    other, _fruit = cats

    def _make(name):
        return Product.objects.create(name=name, source=Product.Source.AUTO, category_fk=other)

    return _make


def run(rules="metadata,dish", apply=True):
    call_command("mg_prune_auto_products", rules=rules, **({"apply": True} if apply else {}))


class TestMetadataRule:
    """Правило работает по названию, база для этого не нужна."""

    @pytest.mark.parametrize(
        "name",
        [
            "Время приготовления 40 мин",
            "40 мин",
            "Итальянская кухня",
            "Завтрак",
            "Выше",
            "Очищенный",
            "Чёрный",
            "Вегетарианские",
        ],
    )
    def test_разметка_страницы_это_мусор(self, name):
        assert is_metadata(name) is True

    @pytest.mark.parametrize("name", ["Бекон копчёный", "Соль мелкая", "Морской коктейль", "Хлопья темпура"])
    def test_настоящий_продукт_не_мусор(self, name):
        assert is_metadata(name) is False

    @pytest.mark.parametrize("name", ["Мороженое", "Заливное", "Жаркое"])
    def test_прилагательное_бывает_продуктом(self, name):
        """По форме прилагательное, по смыслу еда — окончания -ое/-ее не трогаем."""
        assert is_metadata(name) is False


@pytest.mark.django_db
class TestPrune:
    def test_разметка_удаляется(self, auto):
        junk = auto("Время приготовления 40 мин")

        run()

        assert not Product.objects.filter(pk=junk.pk).exists()

    def test_название_блюда_удаляется(self, auto):
        """Признак берём из своей же базы: так называется рецепт, а не продукт."""
        Recipe.objects.create(title="Рататуй")
        dish = auto("Рататуй")

        run()

        assert not Product.objects.filter(pk=dish.pk).exists()

    def test_продукт_из_прочего_остаётся(self, auto):
        """«Прочее» — не метка ошибки: соль и бекон просто не разложились."""
        good = auto("Бекон копчёный")

        run()

        assert Product.objects.filter(pk=good.pk).exists()

    def test_без_apply_ничего_не_трогаем(self, auto):
        junk = auto("Итальянская кухня")

        run(apply=False)

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_правило_all_забирает_всё(self, auto):
        """Широкий отбор остался, но включается только руками."""
        good = auto("Бекон копчёный")

        run(rules="all")

        assert not Product.objects.filter(pk=good.pk).exists()

    def test_неизвестное_правило_ничего_не_делает(self, auto):
        junk = auto("Итальянская кухня")

        run(rules="metdata")

        assert Product.objects.filter(pk=junk.pk).exists()


@pytest.mark.django_db
class TestUntouchable:
    def test_продукт_из_холодильника_не_трогаем(self, auto, django_user_model):
        """Машинный он или нет, но им пользуются."""
        from apps.family.models import Family
        from apps.fridge.models import FridgeItem

        junk = auto("Итальянская кухня")
        owner = django_user_model.objects.create_user(email="u@example.com", password="pass12345", name="У")
        family = Family.objects.create(name="Семья", owner=owner)
        FridgeItem.objects.create(family=family, product=junk, name=junk.name, quantity=1)

        run()

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_продукт_с_синонимом_не_трогаем(self, auto):
        """Синоним заводит редактор — значит запись уже разобрали руками."""
        junk = auto("Итальянская кухня")
        ProductAlias.objects.create(product=junk, alias_norm="итальянская кухня")

        run()

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_выверенный_продукт_не_трогаем(self, cats):
        """source=manual — завёл человек, категория тут ни при чём."""
        other, _fruit = cats
        mine = Product.objects.create(name="Итальянская кухня", source=Product.Source.MANUAL, category_fk=other)

        run()

        assert Product.objects.filter(pk=mine.pk).exists()

    def test_машинный_продукт_с_категорией_не_трогаем(self, cats):
        """Категорию назвал канонизатор — этот сегмент он разобрал."""
        _other, fruit = cats
        good = Product.objects.create(name="Чёрный", source=Product.Source.AUTO, category_fk=fruit)

        run()

        assert Product.objects.filter(pk=good.pk).exists()

    def test_связь_рецепта_переживает_удаление(self, auto):
        """Список покупок берёт название и категорию из самой связи."""
        junk = auto("Время приготовления 40 мин")
        recipe = Recipe.objects.create(title="Салат")
        RecipeProduct.objects.create(
            recipe=recipe,
            product=junk,
            name_raw="время приготовления 40 мин",
            name_canonical="Время приготовления 40 мин",
            category_slug="other",
        )

        run()

        link = RecipeProduct.objects.get(recipe=recipe)
        assert link.product_id is None
        assert link.name_canonical == "Время приготовления 40 мин"
