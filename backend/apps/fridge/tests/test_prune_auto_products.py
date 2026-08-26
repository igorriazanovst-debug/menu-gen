"""MG_AUTOPROD2: разбор того, что машина уже насыпала в каталог.

Команда убирает записи `source=auto`, которые попали в «Прочее» (так помечается
ингредиент, который канонизатор не разобрал) и на которые никто не ссылается.
Проверять здесь надо не «удалилось ли», а границы: чужого не тронуть.

- продукт, лежащий у кого-то в холодильнике, — живой, даже если машинный;
- продукт с выверенным синонимом из админки — тоже;
- продукт с настоящей категорией ИИ разобрал, значит название осмысленное;
- связь рецепта удаление переживает: название и категория лежат в ней самой.
"""

import pytest
from django.core.management import call_command

from apps.fridge.models import Product, ProductAlias, ProductCategory
from apps.recipes.models import Recipe, RecipeProduct


@pytest.fixture
def cats(db):
    other, _ = ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее", "is_active": True})
    fruit, _ = ProductCategory.objects.get_or_create(slug="fruit", defaults={"name_ru": "Фрукты", "is_active": True})
    return other, fruit


@pytest.fixture
def junk(cats):
    other, _fruit = cats
    return Product.objects.create(name="2 яйца вареных", source=Product.Source.AUTO, category_fk=other)


def run(apply=False):
    call_command("mg_prune_auto_products", **({"apply": True} if apply else {}))


@pytest.mark.django_db
class TestPrune:
    def test_мусор_удаляется(self, junk):
        run(apply=True)

        assert not Product.objects.filter(pk=junk.pk).exists()

    def test_без_apply_ничего_не_трогаем(self, junk):
        run()

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_продукт_из_холодильника_не_трогаем(self, junk, django_user_model):
        """Машинный он или нет, но им пользуются."""
        from apps.family.models import Family
        from apps.fridge.models import FridgeItem

        owner = django_user_model.objects.create_user(email="u@example.com", password="pass12345", name="У")
        family = Family.objects.create(name="Семья", owner=owner)
        FridgeItem.objects.create(family=family, product=junk, name=junk.name, quantity=1)

        run(apply=True)

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_продукт_с_синонимом_не_трогаем(self, junk):
        """Синоним заводит редактор — значит запись уже разобрали руками."""
        ProductAlias.objects.create(product=junk, alias_norm="яйца вареные")

        run(apply=True)

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_продукт_с_настоящей_категорией_не_трогаем(self, cats):
        """Категорию назвал канонизатор — этот сегмент он разобрал."""
        _other, fruit = cats
        good = Product.objects.create(name="Слива", source=Product.Source.AUTO, category_fk=fruit)

        run(apply=True)

        assert Product.objects.filter(pk=good.pk).exists()

    def test_выверенный_продукт_не_трогаем(self, cats):
        """source=manual — завёл человек, категория тут ни при чём."""
        other, _fruit = cats
        mine = Product.objects.create(name="Мамина аджика", source=Product.Source.MANUAL, category_fk=other)

        run(apply=True)

        assert Product.objects.filter(pk=mine.pk).exists()

    def test_связь_рецепта_переживает_удаление(self, junk):
        """Список покупок берёт название и категорию из самой связи."""
        recipe = Recipe.objects.create(title="Салат")
        RecipeProduct.objects.create(
            recipe=recipe,
            product=junk,
            name_raw="2 яйца вареных",
            name_canonical="2 яйца вареных",
            category_slug="other",
        )

        run(apply=True)

        link = RecipeProduct.objects.get(recipe=recipe)
        assert link.product_id is None
        assert link.name_canonical == "2 яйца вареных"
