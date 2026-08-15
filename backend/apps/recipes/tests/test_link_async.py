"""MG_LINKASYNC: сохранение рецепта не должно ждать ИИ.

Связи рецепт→продукт строит модель: каждый сегмент состава уходит на
канонизацию, при `AI_TIMEOUT=30` и разбиении по 30 сегментов это легко два
чанка плюс повторный проход. Пока это висело в post_save, сохранение в админке
регулярно отдавало `504 Gateway Time-out`.

Теперь пересборка уходит в Celery и только когда состав действительно
изменился: правка названия, флагов или фото ИИ не касается.
"""

from unittest.mock import patch

import pytest

from apps.recipes.models import Recipe
from apps.recipes.signals import ingredients_changed

INGREDIENTS = [{"name": "Картофель", "grams": 300}, {"name": "Масло", "grams": 20}]


@pytest.fixture
def recipe(db):
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
        return Recipe.objects.create(title="Пюре", ingredients=INGREDIENTS)


@pytest.fixture
def enqueue():
    """Постановка задачи в очередь — единственное, что должен делать сигнал."""
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay") as m:
        yield m


@pytest.mark.django_db(transaction=True)
class TestOnlyOnIngredientChange:
    def test_правка_названия_не_дёргает_ии(self, recipe, enqueue):
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.title = "Картофельное пюре"
        fresh.save()

        enqueue.assert_not_called()

    def test_правка_состава_ставит_задачу(self, recipe, enqueue):
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients = INGREDIENTS + [{"name": "Молоко", "grams": 100}]
        fresh.save()

        enqueue.assert_called_once_with(recipe.pk)

    def test_новый_рецепт_ставит_задачу(self, db, enqueue):
        created = Recipe.objects.create(title="Новый", ingredients=INGREDIENTS)

        enqueue.assert_called_once_with(created.pk)

    def test_рецепт_без_состава_канонизировать_нечего(self, db, enqueue):
        Recipe.objects.create(title="Пустой", ingredients=[])

        enqueue.assert_not_called()

    def test_повторное_сохранение_не_ставит_вторую_задачу(self, recipe, enqueue):
        """Админка сохраняет форму и инлайны отдельно — это два save()."""
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients = [{"name": "Морковь", "grams": 100}]
        fresh.save()
        fresh.save()

        assert enqueue.call_count == 1

    def test_явный_флаг_пропуска_уважается(self, recipe, enqueue):
        """Импортёры выставляют его, чтобы не будить ИИ на каждой строке."""
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients = [{"name": "Лук", "grams": 50}]
        fresh._mg_skip_link_rebuild = True
        fresh.save()

        enqueue.assert_not_called()


@pytest.mark.django_db
class TestIngredientsChanged:
    def test_объект_собран_в_коде_считаем_изменённым(self):
        """Снимка нет — лучше лишняя пересборка, чем потерянные связи."""
        obj = Recipe(title="Из кода", ingredients=INGREDIENTS)

        assert ingredients_changed(obj, created=False) is True

    def test_порядок_ключей_не_считается_изменением(self, recipe):
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients = [
            {"grams": 300, "name": "Картофель"},
            {"grams": 20, "name": "Масло"},
        ]

        assert ingredients_changed(fresh, created=False) is False

    def test_правка_на_месте_замечается(self, recipe):
        """Снимок — отпечаток, а не ссылка на тот же список."""
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients[0]["grams"] = 500

        assert ingredients_changed(fresh, created=False) is True


@pytest.mark.django_db
class TestTask:
    def test_задача_зовёт_пересборку(self, recipe):
        from apps.recipes.tasks import rebuild_recipe_links_task

        with patch("apps.recipes.recipe_products.rebuild_recipe_links", return_value=3) as rebuild:
            result = rebuild_recipe_links_task(recipe.pk)

        assert result == 3
        assert rebuild.call_args.args[0].pk == recipe.pk

    def test_удалённый_рецепт_не_ошибка(self, db):
        from apps.recipes.tasks import rebuild_recipe_links_task

        assert rebuild_recipe_links_task(10**9) == 0


@pytest.mark.django_db(transaction=True)
class TestBrokerDown:
    def test_недоступный_брокер_не_роняет_сохранение(self, recipe, caplog):
        """Иначе админка отдаст 500 вместо сохранённого рецепта."""
        fresh = Recipe.objects.get(pk=recipe.pk)
        fresh.ingredients = [{"name": "Свёкла", "grams": 100}]

        with patch(
            "apps.recipes.tasks.rebuild_recipe_links_task.delay",
            side_effect=OSError("broker unreachable"),
        ):
            fresh.save()

        fresh.refresh_from_db()
        assert fresh.ingredients == [{"name": "Свёкла", "grams": 100}]
        assert "mg_backfill_recipe_products" in caplog.text
