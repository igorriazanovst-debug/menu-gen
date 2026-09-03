"""MG_SUITABLE: разметка приёмов не должна расходиться с ролями генератора.

Проверяется то, что уже один раз стоило дорого: десерты и выпечка были помечены
как годные для перекуса, хотя роли «десерт» и «выпечка» существуют только в
обеде. Генератор доставал 5 десертов из 45, и это читалось как нехватка пула.

Три уровня защиты, каждый со своим тестом:

* таблица «роль → приёмы» выводится из генератора, а не переписана руками;
* команда чинит недостижимую разметку и не трогает нормальную;
* словарь импорта say7 согласован с ролями генератора — иначе следующая
  выгрузка привезёт ту же поломку.

Названия рецептов выдуманные: в тестовой базе есть посевной каталог продуктов
(миграция fridge 0004), но не рецепты.
"""

import pytest
from django.core.management import call_command

from apps.recipes.management.commands.mg_fix_suitable_for import needed_meals_by_role
from apps.recipes.models import Recipe


def _recipe(dish_type, suitable_for, title="Блюдо для проверки"):
    return Recipe.objects.create(
        title=title,
        dish_type=dish_type,
        suitable_for=suitable_for,
        is_published=True,
    )


def test_table_comes_from_the_generator():
    """Роли берутся из MEAL_COMPONENTS, а не из копии рядом с командой."""
    need = needed_meals_by_role()
    # Десерт и выпечка живут только в обеде — из-за этого всё и сломалось.
    assert need["dessert"] == {"lunch"}
    assert need["bakery"] == {"lunch"}
    # Основное и салат — в обеде и ужине.
    assert need["main"] == {"lunch", "dinner"}
    assert need["salad"] == {"lunch", "dinner"}
    assert need["breakfast_dish"] == {"breakfast"}
    assert need["snack"] == {"snack"}


def test_import_say7_mapping_agrees_with_the_generator():
    """Словарь импорта не должен объявлять блюдо годным только туда, куда оно не попадёт."""
    from apps.recipes.management.commands.import_say7_recipes import SUITABLE_BY_DISH

    need = needed_meals_by_role()
    broken = {
        dish: meals
        for dish, meals in SUITABLE_BY_DISH.items()
        if dish in need and meals and not (set(meals) & need[dish])
    }
    assert not broken, f"разметка импорта недостижима для: {broken}"


@pytest.mark.django_db
def test_dry_run_changes_nothing():
    recipe = _recipe("dessert", ["snack"], "Сухой прогон не пишет")
    call_command("mg_fix_suitable_for")
    recipe.refresh_from_db()
    assert recipe.suitable_for == ["snack"]


@pytest.mark.django_db
def test_apply_adds_the_missing_meal():
    recipe = _recipe("dessert", ["snack"], "Десерт из перекуса")
    call_command("mg_fix_suitable_for", "--apply")
    recipe.refresh_from_db()
    # Обед добавлен, перекус не потерян: ничего не удаляем.
    assert set(recipe.suitable_for) == {"snack", "lunch"}


@pytest.mark.django_db
def test_reachable_markup_is_left_alone():
    recipe = _recipe("main", ["dinner"], "Ужинное основное")
    call_command("mg_fix_suitable_for", "--apply")
    recipe.refresh_from_db()
    assert recipe.suitable_for == ["dinner"]


@pytest.mark.django_db
def test_empty_markup_is_left_alone():
    """Пусто означает «годится везде» — фильтр генератора такие пропускает."""
    recipe = _recipe("dessert", [], "Без разметки")
    call_command("mg_fix_suitable_for", "--apply")
    recipe.refresh_from_db()
    assert recipe.suitable_for == []


@pytest.mark.django_db
def test_apply_is_idempotent():
    recipe = _recipe("bakery", ["breakfast"], "Выпечка к завтраку")
    call_command("mg_fix_suitable_for", "--apply")
    recipe.refresh_from_db()
    first = list(recipe.suitable_for)
    call_command("mg_fix_suitable_for", "--apply")
    recipe.refresh_from_db()
    assert recipe.suitable_for == first
