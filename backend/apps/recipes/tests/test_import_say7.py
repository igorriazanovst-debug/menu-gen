"""MG_SAY7: импорт выгрузки say7 — это классификация, а не перекладывание полей.

В источнике есть состав, шаги, КБЖУ на 100 г и рубрика сайта. Всего, чем живёт
генератор меню, там нет, поэтому проверять надо именно выводы:

- рубрика сайта → наш тип блюда, включая две смешанные рубрики;
- вес порции — из веса готового блюда и числа порций, с отсевом бессмыслицы;
- КБЖУ порции — произведение, а не отдельные данные;
- диет-флаги и время готовки — из состава и шагов.

И отдельно то, что легко потерять при доработках: рецепты приходят БЕЗ
публикации (у них нет фотографий), повторный импорт не плодит дубли и не
перехватывает чужой рецепт с тем же названием.
"""

import gzip
import json
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.recipes.models import Recipe
from apps.recipes.management.commands.import_say7_recipes import (
    cook_time_for,
    cooking_method_for,
    diet_flags,
    dish_type_for,
    normalize_units,
    portion_grams,
)

ROW = {
    "site_id": 4242,
    "name": "Гречка с грибами",
    "category": "Вторые блюда",
    "yield_text": "4 порции",
    "servings_min": 4,
    "servings_max": 4,
    "cooked_weight_g": 1000,
    "yield_weight_g": None,
    "kcal_100g": 120.0,
    "protein_100g": 4.0,
    "fat_100g": 3.0,
    "carbs_100g": 18.0,
    # Единицы в выгрузке — латинские коды парсера, ровно как в файле.
    "ingredients": [
        {"name": "Гречка", "quantity": "1", "unit": "cup", "grams": 200},
        {"name": "Шампиньоны", "quantity": "300", "unit": "g", "grams": 300},
        {"name": "Масло растительное", "quantity": "2", "unit": "tbsp", "grams": 30},
    ],
    "steps": ["Промыть гречку.", "Обжарить грибы 10 минут.", "Варить 15 минут под крышкой."],
}


@pytest.fixture
def data_file(tmp_path):
    def _make(rows):
        p = tmp_path / "say7.jsonl.gz"
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return str(p)

    return _make


class TestDishType:
    def test_рубрика_превращается_в_тип_блюда(self):
        assert dish_type_for("Первые блюда", "Борщ") == "soup"
        assert dish_type_for("Салаты", "Оливье") == "salad"
        assert dish_type_for("Блины, оладьи, сырники", "Сырники") == "breakfast_dish"

    def test_смешанная_рубрика_уточняется_названием(self):
        """«Десерты, напитки» — одна рубрика на два наших типа."""
        assert dish_type_for("Десерты, напитки", "Малиновое мороженое") == "dessert"
        assert dish_type_for("Десерты, напитки", "Глинтвейн с брусникой") == "drink"

    def test_разное_это_почти_всегда_соус(self):
        assert dish_type_for("Разное", "Томатный соус") == "sauce"
        assert dish_type_for("Разное", "Домашняя лапша яичная") == "snack"


class TestPortion:
    def test_вес_порции_из_веса_блюда_и_порций(self):
        assert portion_grams(ROW) == 250

    def test_без_числа_порций_вес_не_выдумываем(self):
        assert portion_grams({**ROW, "servings_min": None, "servings_max": None}) is None

    def test_бессмысленный_вес_отбрасываем(self):
        """Порция в пять граммов или в три кило — ошибка данных, а не блюдо.

        Пустое поле видно редактору, неверное — нет.
        """
        assert portion_grams({**ROW, "cooked_weight_g": 20, "servings_min": 4}) is None
        assert portion_grams({**ROW, "cooked_weight_g": 12000, "servings_min": 4}) is None


class TestUnits:
    """Единицы в выгрузке — коды парсера, а не то, что читает человек.

    Дело не только в виде карточки: список покупок складывает количества по
    своей таблице единиц, и кода «g» в ней нет — «700 g» и «300 г» окажутся в
    списке двумя разными строками.
    """

    def test_коды_переводятся_в_наши_токены(self):
        out = normalize_units([{"name": "Мука", "unit": "g"}, {"name": "Молоко", "unit": "ml"}])

        assert [i["unit"] for i in out] == ["г", "мл"]

    def test_ложки_и_штуки_тоже(self):
        rows = [{"unit": "tbsp"}, {"unit": "tsp"}, {"unit": "piece"}, {"unit": "cup"}]

        assert [i["unit"] for i in normalize_units(rows)] == ["ст.л.", "ч.л.", "шт", "стакан"]

    def test_незнакомую_единицу_не_выдумываем(self):
        """Пустое или непонятное поле видно редактору, подменённое — нет."""
        rows = [{"unit": "щепотка"}, {"unit": ""}, {}]

        assert [i["unit"] for i in normalize_units(rows)] == ["щепотка", "", ""]

    def test_остальные_поля_на_месте(self):
        out = normalize_units([{"name": "Мука", "quantity": "2", "unit": "g", "grams": 100}])

        assert out[0] == {"name": "Мука", "quantity": "2", "unit": "г", "grams": 100}


class TestFromSteps:
    def test_время_складывается_из_шагов(self):
        assert cook_time_for(["Обжарить 10 минут.", "Варить 15 минут."]) == 25

    def test_часы_переводятся_в_минуты(self):
        assert cook_time_for(["Тушить 1 час."]) == 60

    def test_способ_приготовления_по_глаголам(self):
        assert cooking_method_for(["Запекать в духовке 40 минут."]) == "baked"
        assert cooking_method_for(["Обжарить на сковороде."]) == "fried"
        assert cooking_method_for(["Нарезать и подать."]) == ""


class TestDietFlags:
    def test_мясное_блюдо_не_вегетарианское(self):
        f = diet_flags([{"name": "Говядина"}, {"name": "Лук репчатый"}])

        assert f["is_vegetarian"] is False and f["is_vegan"] is False

    def test_овощное_веганское(self):
        f = diet_flags([{"name": "Огурцы"}, {"name": "Помидоры"}])

        assert f["is_vegan"] is True and f["is_lactose_free"] is True

    def test_молочное_вегетарианское_но_не_веганское(self):
        f = diet_flags([{"name": "Творог"}, {"name": "Яйцо куриное"}])

        assert f["is_vegetarian"] is True
        assert f["is_vegan"] is False
        assert f["is_lactose_free"] is False

    def test_мука_это_глютен(self):
        assert diet_flags([{"name": "Мука пшеничная"}])["is_gluten_free"] is False
        assert diet_flags([{"name": "Рис"}])["is_gluten_free"] is True


@pytest.mark.django_db
class TestImport:
    def test_рецепт_заводится_с_классификацией(self, data_file):
        call_command("import_say7_recipes", file=data_file(ROW and [ROW]))

        r = Recipe.objects.get(legacy_id="say7:4242")
        assert r.title == "Гречка с грибами"
        assert r.dish_type == "main"
        assert r.suitable_for == ["lunch", "dinner"]
        assert r.portion_g == 250
        assert float(r.kcal_per_100g) == 120.0
        # «Обжарить» характернее «варить» — так задан приоритет в METHOD_WORDS.
        assert r.cooking_method == "fried"
        assert r.cook_time_min == 25
        assert len(r.steps) == 3 and r.steps[0]["order"] == 1

    def test_кбжу_порции_считается_из_ста_граммов(self, data_file):
        """250 г порции при 120 ккал/100 г — это 300 ккал."""
        call_command("import_say7_recipes", file=data_file([ROW]))

        r = Recipe.objects.get(legacy_id="say7:4242")
        assert float(r.kcal) == 300.0
        assert float(r.proteins) == 10.0

    def test_без_веса_порции_кбжу_порции_не_выдумываем(self, data_file):
        row = {**ROW, "servings_min": None, "servings_max": None}

        call_command("import_say7_recipes", file=data_file([row]))

        r = Recipe.objects.get(legacy_id="say7:4242")
        assert r.portion_g is None
        assert r.kcal is None

    def test_импортируются_без_публикации(self, data_file):
        """У рецептов нет фотографий: карточка без фото выглядит поломкой."""
        call_command("import_say7_recipes", file=data_file([ROW]))

        assert Recipe.objects.filter(is_published=True).count() == 0

    def test_повторный_импорт_не_плодит_дубли(self, data_file):
        f = data_file([ROW])
        call_command("import_say7_recipes", file=f)
        call_command("import_say7_recipes", file=f)

        assert Recipe.objects.filter(legacy_id="say7:4242").count() == 1

    def test_чужой_рецепт_с_тем_же_названием_не_трогаем(self, data_file):
        """Тот же рецепт мог приехать раньше из другого источника."""
        Recipe.objects.create(title="Гречка с грибами", legacy_id="tg:99", is_published=True)

        call_command("import_say7_recipes", file=data_file([ROW]))

        assert Recipe.objects.filter(title="Гречка с грибами").count() == 1
        survivor = Recipe.objects.get(title="Гречка с грибами")
        assert survivor.legacy_id == "tg:99"
        assert survivor.is_published is True

    def test_рецепт_заведённый_руками_тоже_чужой(self, data_file):
        """Пустой legacy_id — это ручная запись из админки.

        Раньше такой рецепт считался «своим» и перезаписывался целиком: терял
        фотографию, содержимое и публикацию. Самый обидный случай — редактор
        завёл карточку с фото, а импорт её обнулил.
        """
        Recipe.objects.create(
            title="Гречка с грибами",
            image_url="/media/recipes/grechka.jpg",
            is_published=True,
        )

        call_command("import_say7_recipes", file=data_file([ROW]))

        assert Recipe.objects.filter(title="Гречка с грибами").count() == 1
        survivor = Recipe.objects.get(title="Гречка с грибами")
        assert survivor.image_url == "/media/recipes/grechka.jpg"
        assert survivor.is_published is True
        assert survivor.legacy_id is None

    def test_состав_приходит_с_русскими_единицами(self, data_file):
        call_command("import_say7_recipes", file=data_file([ROW]))

        r = Recipe.objects.get(legacy_id="say7:4242")
        assert [i["unit"] for i in r.ingredients] == ["стакан", "г", "ст.л."]

    def test_dry_run_ничего_не_пишет(self, data_file):
        call_command("import_say7_recipes", file=data_file([ROW]), dry_run=True)

        assert Recipe.objects.count() == 0


@pytest.mark.django_db(transaction=True)
class TestNoPerRecipeAI:
    """Задача пересборки связей ставится в on_commit — нужна настоящая транзакция.

    На сохранении рецепта висит сигнал, который ставит эту задачу, а она ходит
    в ИИ на каждый рецепт отдельно. Полторы тысячи строк — полторы тысячи
    обращений к платному провайдеру вместо примерно сорока, если тот же состав
    канонизировать пачками. Пачками это делает mg_backfill_recipe_products, он
    и указан в подсказке после импорта.
    """

    def test_импорт_не_ставит_задачу_на_каждый_рецепт(self, data_file):
        with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay") as enqueue:
            call_command("import_say7_recipes", file=data_file([ROW]))

        enqueue.assert_not_called()

    def test_обычное_сохранение_задачу_ставит(self, data_file):
        """Контроль: сигнал жив, и молчание выше — заслуга импорта, а не поломки."""
        call_command("import_say7_recipes", file=data_file([ROW]))
        r = Recipe.objects.get(legacy_id="say7:4242")

        with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay") as enqueue:
            r.ingredients = ROW["ingredients"] + [{"name": "Соль", "unit": "g", "grams": 5}]
            r.save()

        enqueue.assert_called_once_with(r.pk)
