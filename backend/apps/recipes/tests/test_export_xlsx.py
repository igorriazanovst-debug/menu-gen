"""MG_RECIPEXLSX: таблица рецептов для работы редактора.

Таблицей обходят импортированные рецепты и доснимают к ним фото, поэтому важны
две вещи: чтобы в ячейке был весь рецепт целиком (шаги с номерами, состав с
количествами), и чтобы ссылка вела туда, где фото загружают.

Про ссылку отдельно: у карточки рецепта нет своего адреса во фронте — роут
только `/recipes`, а `?id=` страница не читает. Поэтому по умолчанию ставится
адрес админки, и это проверяется тестом: подмена его на неработающий адрес
приложения обесценила бы всю таблицу.
"""

import csv
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.recipes.models import Recipe

ROW = {
    "title": "Гречка с грибами",
    "legacy_id": "say7:4242",
    "steps": [{"text": "Промыть гречку.", "order": 1}, {"text": "Обжарить грибы.", "order": 2}],
    "ingredients": [
        {"name": "Гречка", "quantity": "1", "unit": "стакан", "grams": 200},
        {"name": "Соль", "quantity": "", "unit": "", "grams": None},
    ],
}


@pytest.fixture
def recipe(db):
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
        return Recipe.objects.create(**ROW)


def читать_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh, delimiter=";"))


class TestТекстЯчеек:
    def test_шаги_с_номерами_в_одной_ячейке(self, recipe):
        from apps.recipes.management.commands.mg_export_recipes_xlsx import steps_text

        assert steps_text(recipe) == "1. Промыть гречку.\n2. Обжарить грибы."

    def test_состав_с_количеством_и_весом(self, recipe):
        from apps.recipes.management.commands.mg_export_recipes_xlsx import ingredients_text

        assert ingredients_text(recipe) == "Гречка — 1 стакан (200 г)\nСоль"

    def test_пустые_количества_не_дают_висящих_знаков(self, db):
        """«Соль — ()» читается хуже, чем просто «Соль»."""
        from apps.recipes.management.commands.mg_export_recipes_xlsx import ingredients_text

        with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
            r = Recipe.objects.create(title="Т", ingredients=[{"name": "Соль", "quantity": "", "grams": None}])

        assert ingredients_text(r) == "Соль"


@pytest.mark.django_db
class TestВыгрузка:
    def test_колонки_и_строка(self, recipe, tmp_path):
        out = str(tmp_path / "t.csv")

        call_command("mg_export_recipes_xlsx", "--csv", "--out", out)

        rows = читать_csv(out)
        assert rows[0] == ["ID", "Название", "Шаги", "Состав", "Ссылка"]
        assert rows[1][0] == str(recipe.id)
        assert rows[1][1] == "Гречка с грибами"

    def test_ссылка_ведёт_в_админку(self, recipe, tmp_path):
        """Рецепты не опубликованы, и фото грузят в админке — туда и ссылка."""
        out = str(tmp_path / "t.csv")

        call_command("mg_export_recipes_xlsx", "--csv", "--out", out)

        assert читать_csv(out)[1][4] == "https://menugen.ru/admin/recipes/recipe/%s/change/" % recipe.id

    def test_адрес_сайта_подменяется(self, recipe, tmp_path):
        out = str(tmp_path / "t.csv")

        call_command("mg_export_recipes_xlsx", "--csv", "--out", out, "--base-url", "http://31.192.110.121:8081")

        assert читать_csv(out)[1][4].startswith("http://31.192.110.121:8081/admin/")

    def test_выгружается_только_нужный_источник(self, recipe, tmp_path):
        """В базе тысячи чужих рецептов — таблица нужна по одному импорту."""
        with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
            Recipe.objects.create(title="Чужой", legacy_id="tg:1")
        out = str(tmp_path / "t.csv")

        call_command("mg_export_recipes_xlsx", "--csv", "--out", out)

        rows = читать_csv(out)
        assert len(rows) == 2 and rows[1][1] == "Гречка с грибами"

    def test_xlsx_читается_обратно(self, recipe, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        out = str(tmp_path / "t.xlsx")

        call_command("mg_export_recipes_xlsx", "--out", out)

        ws = openpyxl.load_workbook(out).active
        assert [c.value for c in ws[1]] == ["ID", "Название", "Шаги", "Состав", "Ссылка"]
        assert ws.cell(row=2, column=3).value == "1. Промыть гречку.\n2. Обжарить грибы."


# ── MG_UNUSABLE: отбор негодных к публикации ────────────────────────────────
#
# Негоден тот, у кого нет веса порции или калорий на порцию: снять и
# опубликовать его можно, но генератор меню его никогда не возьмёт — без веса
# порции он не проходит ни коридор калорий, ни «Тарелку». Таблица нужна, чтобы
# такие рецепты не попали в работу фотографа.


def _recipe(title, **kwargs):
    with patch("apps.recipes.tasks.rebuild_recipe_links_task.delay"):
        return Recipe.objects.create(
            title=title,
            legacy_id="say7:%s" % (abs(hash(title)) % 10000),
            steps=[],
            ingredients=[],
            **kwargs,
        )


class TestОтборНегодных:
    def test_берутся_только_без_веса_или_калорий(self, db, tmp_path):
        годный = _recipe("Годный", is_published=False, portion_g=250, kcal=300)
        без_веса = _recipe("Без веса", is_published=False, portion_g=None, kcal=300)
        без_ккал = _recipe("Без калорий", is_published=False, portion_g=250, kcal=None)
        путь = tmp_path / "out.csv"

        call_command("mg_export_recipes_xlsx", "--csv", "--unpublished", "--missing-portion", "--out", str(путь))

        строки = читать_csv(путь)
        ids = {row[0] for row in строки[1:]}
        assert ids == {str(без_веса.id), str(без_ккал.id)}
        assert str(годный.id) not in ids

    def test_опубликованные_не_попадают(self, db, tmp_path):
        _recipe("Опубликованный без веса", is_published=True, portion_g=None, kcal=None)
        путь = tmp_path / "out.csv"

        call_command("mg_export_recipes_xlsx", "--csv", "--unpublished", "--missing-portion", "--out", str(путь))

        assert читать_csv(путь)[1:] == []

    def test_есть_колонки_с_причиной(self, db, tmp_path):
        _recipe("Без веса", is_published=False, portion_g=None, kcal=None, dish_type="soup")
        путь = tmp_path / "out.csv"

        call_command("mg_export_recipes_xlsx", "--csv", "--unpublished", "--missing-portion", "--out", str(путь))

        строки = читать_csv(путь)
        # Пять исходных колонок плюс шесть объясняющих: без них таблица
        # утверждает «эти плохие» и не даёт проверить утверждение.
        assert строки[0][5:] == ["Тип блюда", "Порций", "Вес порции", "Ккал/порция", "Ккал/100 г", "Фото"]
        assert строки[1][5] == "soup"
        assert строки[1][10] == "нет"

    def test_без_флага_колонок_с_причиной_нет(self, recipe, tmp_path):
        """Обычная выгрузка для фотографа не должна поменять форму."""
        путь = tmp_path / "out.csv"
        call_command("mg_export_recipes_xlsx", "--csv", "--out", str(путь))
        assert читать_csv(путь)[0] == ["ID", "Название", "Шаги", "Состав", "Ссылка"]

    def test_только_без_фото(self, db, tmp_path):
        без_фото = _recipe("Без фото", is_published=False, portion_g=None, image_url="")
        _recipe("С фото", is_published=False, portion_g=None, image_url="https://x/y.jpg")
        путь = tmp_path / "out.csv"

        call_command(
            "mg_export_recipes_xlsx",
            "--csv",
            "--unpublished",
            "--missing-portion",
            "--no-photo",
            "--out",
            str(путь),
        )

        строки = читать_csv(путь)
        assert {row[0] for row in строки[1:]} == {str(без_фото.id)}

    def test_пустая_строка_и_null_считаются_одинаково(self, db, tmp_path):
        """Часть импортов пишет NULL, часть — пустую строку; терять нельзя ни тех, ни других."""
        пусто = _recipe("Пустая строка", is_published=False, portion_g=None, image_url="")
        нуль = _recipe("NULL", is_published=False, portion_g=None, image_url=None)
        путь = tmp_path / "out.csv"

        call_command(
            "mg_export_recipes_xlsx",
            "--csv",
            "--unpublished",
            "--missing-portion",
            "--no-photo",
            "--out",
            str(путь),
        )

        строки = читать_csv(путь)
        assert {row[0] for row in строки[1:]} == {str(пусто.id), str(нуль.id)}

    def test_исключение_типа_блюда(self, db, tmp_path):
        суп = _recipe("Суп", is_published=False, portion_g=None, dish_type="soup", image_url="")
        десерт = _recipe("Десерт", is_published=False, portion_g=None, dish_type="dessert", image_url="")
        путь = tmp_path / "out.csv"

        call_command(
            "mg_export_recipes_xlsx",
            "--csv",
            "--unpublished",
            "--missing-portion",
            "--no-photo",
            "--exclude-dish",
            "soup",
            "--out",
            str(путь),
        )

        строки = читать_csv(путь)
        ids = {row[0] for row in строки[1:]}
        assert ids == {str(десерт.id)}
        assert str(суп.id) not in ids


class TestУдалениеЧитаетВыгрузку:
    """Выгрузка и удаление должны стыковаться без ручной правки файла.

    Команда удаления читала колонку «id» строчными и запятую как разделитель, а
    выгрузка пишет «ID» и «;». Несовпадение не давало ошибки: команда сообщала
    «в CSV записей с id: 0» и молча ничего не удаляла.
    """

    def test_сухой_прогон_видит_строки_выгрузки(self, db, tmp_path, capsys):
        рецепт = _recipe("На удаление", is_published=False, portion_g=None, image_url="")
        путь = tmp_path / "out.csv"
        call_command("mg_export_recipes_xlsx", "--csv", "--unpublished", "--missing-portion", "--out", str(путь))

        call_command("delete_recipes_from_csv", "--file", str(путь))

        assert Recipe.objects.filter(id=рецепт.id).exists(), "сухой прогон не должен удалять"
        assert "В CSV записей с id: 1" in capsys.readouterr().out


class TestРабочийСписокДляСъёмки:
    """Список «что снимать»: неопубликованные без фото, с типом блюда.

    Тип блюда в такой таблице не украшение: снимать надо не подряд, а по ролям,
    которых не хватает генератору (на 04.09 это девять супов и двадцать шесть
    перекусов). Без колонки роли список приходится сверять с базой построчно.
    """

    def test_колонки_добавляются_отдельным_флагом(self, db, tmp_path):
        _recipe("Без фото", is_published=False, portion_g=250, kcal=300, dish_type="soup", image_url="")
        путь = tmp_path / "out.csv"

        call_command(
            "mg_export_recipes_xlsx", "--csv", "--unpublished", "--no-photo", "--diagnostics", "--out", str(путь)
        )

        строки = читать_csv(путь)
        assert строки[0][5] == "Тип блюда"
        assert строки[1][5] == "soup"

    def test_годные_к_публикации_не_отсеиваются(self, db, tmp_path):
        """Без --missing-portion в список идут и те, у кого с весом всё в порядке."""
        годный = _recipe("Годный без фото", is_published=False, portion_g=250, kcal=300, image_url="")
        путь = tmp_path / "out.csv"

        call_command("mg_export_recipes_xlsx", "--csv", "--unpublished", "--no-photo", "--out", str(путь))

        assert {row[0] for row in читать_csv(путь)[1:]} == {str(годный.id)}
