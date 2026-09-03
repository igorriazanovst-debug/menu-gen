"""MG_SUITABLE: разметку приёмов спрашиваем только там, где у роли есть выбор.

Что это чинит (замер на проде, chat-83). Импорт say7 помечал десерты как
`["snack"]`, а выпечку как `["breakfast", "snack"]`. Выглядит разумно — десерт и
правда сойдёт за перекус. Но перекус берёт блюда с `dish_type='snack'`, а не
десерты, и роль «десерт» существует только в обеде. Пометка, где обеда нет, не
выбирала между слотами: она вычёркивала рецепт целиком. Из 45 десертов генератор
доставал 5, из 35 выпечек — 2, и в отчёте это читалось как нехватка пула.

Проверяется три вещи:

* набор ролей с выбором приёма выводится из MEAL_COMPONENTS, а не переписан
  рядом (иначе он разойдётся с раскладкой так же, как разошлась разметка);
* десерт с пометкой «перекус» попадает в обед — то есть пул перестал быть
  недостижимым;
* у роли с выбором приёма фильтр по-прежнему работает: основное блюдо с
  пометкой «ужин» в обед не идёт.

Названия выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не рецепты.
"""

from datetime import date

import pytest

from apps.menu.generator import ROLES_WITH_MEAL_CHOICE, MenuGenerator
from apps.recipes.models import Recipe


class _Member:
    id = 1
    name = "Проверяющий"

    def __init__(self):
        class _U:
            class profile:
                calorie_target = None

        self.user = _U()


def _generator():
    class _Fam:
        id = 1

    return MenuGenerator(
        family=_Fam(),
        members=[_Member()],
        period_days=7,
        start_date=date(2026, 1, 5),
        plan_code="free",
        filters={},
    )


def test_roles_with_choice_are_derived_from_meal_components():
    # Основное и салат встречаются и в обеде, и в ужине — разметка их различает.
    assert "main" in ROLES_WITH_MEAL_CHOICE
    assert "salad" in ROLES_WITH_MEAL_CHOICE
    # У этих слот единственный: спрашивать разметку не о чем.
    for role in ("dessert", "bakery", "soup", "breakfast_dish", "snack"):
        assert role not in ROLES_WITH_MEAL_CHOICE, role


def _recipe(title, dish_type, suitable_for, **kwargs):
    return Recipe.objects.create(
        title=title,
        dish_type=dish_type,
        suitable_for=suitable_for,
        is_published=True,
        portion_g=kwargs.pop("portion_g", 150),
        kcal=kwargs.pop("kcal", 200),
        **kwargs,
    )


def _pick(generator, role, meal_type, pool):
    return generator._pick_for_role(
        role=role,
        meal_type=meal_type,
        pools={role: pool},
        used=set(),
        hard_exclude=set(),
        fridge_ids=set(),
        target_cal=None,
        member_id=1,
        day_offset=0,
    )


@pytest.mark.django_db
def test_dessert_marked_snack_is_reachable_at_lunch():
    """Ровно тот случай, из-за которого сорок десертов были мертвы."""
    dessert = _recipe("Пудинг проверочный", "dessert", ["snack"])
    assert _pick(_generator(), "dessert", "lunch", [dessert]) == dessert


@pytest.mark.django_db
def test_bakery_marked_breakfast_is_reachable_at_lunch():
    bakery = _recipe("Булка проверочная", "bakery", ["breakfast", "snack"])
    assert _pick(_generator(), "bakery", "lunch", [bakery]) == bakery


@pytest.mark.django_db
def test_main_marked_dinner_is_not_taken_for_lunch():
    """У роли с выбором приёма разметка обязана продолжать работать.

    Берётся ужинное блюдо только тогда, когда обеденных не осталось вовсе —
    это запасной путь самого генератора, и он тут ни при чём: в пуле есть
    обеденное, значит выбрано должно быть оно.
    """
    dinner_only = _recipe("Ужинное проверочное", "main", ["dinner"])
    lunch_ok = _recipe("Обеденное проверочное", "main", ["lunch"])
    assert _pick(_generator(), "main", "lunch", [dinner_only, lunch_ok]) == lunch_ok
