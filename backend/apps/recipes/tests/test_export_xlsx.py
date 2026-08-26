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
