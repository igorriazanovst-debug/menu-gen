"""MG_MEALCOUNT: сколько приёмов выбрали — столько и должно быть.

При «трёх приёмах» меню получалось из пяти: завтрак, обед, ужин и два перекуса.
Перекусы дописывали доборы — овощной (MG-304) и калорийный (стратегия 2): они
всегда создавали новые слоты snack1, snack2, дальше snack3 и так до пяти,
независимо от выбранного плана.

Здесь закреплено главное правило: генератор не создаёт приём, которого нет в
плане. Добор кладётся в существующий приём, а если места не осталось — остаток
уходит в предупреждение, а не в новый перекус.
"""

from datetime import date

import pytest

from apps.family.models import Family, FamilyMember
from apps.menu.generator import MEAL_PLAN_3, MEAL_PLAN_5, MenuGenerator
from apps.recipes.models import Recipe
from apps.users.models import Profile, User


def mk(title, food_group, dish_type="main", kcal="100", weight="150.0"):
    return Recipe.objects.create(
        title=title,
        food_group=food_group,
        dish_type=dish_type,
        ingredients=[],
        nutrition={"weight": {"value": weight}, "calories": {"value": kcal}},
        servings=1,
        servings_normalized=1,
        povar_raw={},
    )


@pytest.fixture
def family_with_pool(db):
    user = User.objects.create_user(email="mealcount@test.local", password="x", name="Едок")
    Profile.objects.create(user=user, calorie_target=2000)
    family = Family.objects.create(name="Семья", owner=user)
    member = FamilyMember.objects.create(family=family, user=user, role="adult")

    for i in range(8):
        mk(f"Салат{i}", "vegetable", dish_type="salad")
        mk(f"Горячее{i}", "protein", dish_type="main")
        mk(f"Завтрак{i}", "grain", dish_type="breakfast_dish")
        mk(f"Перекус{i}", "fruit", dish_type="snack")
    return family, member


def generate(family, member, **filters):
    gen = MenuGenerator(
        family=family,
        members=[member],
        period_days=2,
        start_date=date(2026, 6, 1),
        plan_code="free",
        filters=filters,
    )
    return gen, gen.generate()


def slots_of(items):
    return {it["meal_slot"] for it in items}


@pytest.mark.django_db
class TestStrategy1:
    def test_три_приёма_остаются_тремя(self, family_with_pool):
        family, member = family_with_pool

        _, items = generate(family, member, meal_plan_type="3")

        assert slots_of(items) <= set(MEAL_PLAN_3)

    def test_перекусов_не_появляется_даже_при_недоборе_овощей(self, family_with_pool):
        """Раньше именно овощной добор дорисовывал snack1 и snack2."""
        family, member = family_with_pool

        gen, items = generate(family, member, meal_plan_type="3")

        assert not [it for it in items if str(it["meal_slot"]).startswith("snack")]
        # то, что не поместилось, честно уходит в предупреждение
        assert any(w["code"] == "veg_fruit_shortfall" for w in gen.last_warnings)

    def test_пять_приёмов_остаются_пятью(self, family_with_pool):
        family, member = family_with_pool

        _, items = generate(family, member, meal_plan_type="5")

        assert slots_of(items) <= set(MEAL_PLAN_5)
        assert "snack1" in slots_of(items)


@pytest.mark.django_db
class TestStrategy2Topup:
    """Стратегия 2 добирает дневные калории отдельными блюдами — и раньше всегда
    называла их перекусами. Полный прогон s2 требует богатого пула по макро-ролям,
    поэтому проверяем сам добор."""

    def _fill(self, family, member, meal_plan_type):
        gen = MenuGenerator(
            family=family,
            members=[member],
            period_days=1,
            start_date=date(2026, 6, 1),
            plan_code="free",
            filters={"meal_plan_type": meal_plan_type, "strategy": "2"},
        )
        items = []
        pools = {"snack": list(Recipe.objects.filter(dish_type="snack"))}
        gen._fill_snacks_s2(
            items=items,
            member=member,
            day=0,
            used=set(),
            hard_exclude={},
            fridge_ids=set(),
            pools=pools,
            target_cal=2000.0,
        )
        return items

    def test_в_плане_на_три_добор_уходит_в_обед_и_ужин(self, family_with_pool):
        family, member = family_with_pool

        items = self._fill(family, member, "3")

        assert items, "добор вообще должен был случиться"
        assert slots_of(items) <= set(MEAL_PLAN_3)

    def test_в_плане_на_пять_добор_идёт_в_перекусы(self, family_with_pool):
        family, member = family_with_pool

        items = self._fill(family, member, "5")

        assert slots_of(items) <= set(MEAL_PLAN_5)
        assert "snack1" in slots_of(items)

    def test_добор_не_дублирует_роль_в_приёме(self, family_with_pool):
        family, member = family_with_pool

        items = self._fill(family, member, "3")

        keys = [(it["meal_slot"], it["component_role"]) for it in items]
        assert len(keys) == len(set(keys))


@pytest.mark.django_db
class TestSlotHelpers:
    def test_добор_не_занимает_роль_дважды(self, family_with_pool):
        """UNIQUE (меню, член, день, слот, роль): двух салатов в обеде не бывает."""
        family, member = family_with_pool

        _, items = generate(family, member, meal_plan_type="3")

        keys = [(it["member"].id, it["day_offset"], it["meal_slot"], it["component_role"]) for it in items]
        assert len(keys) == len(set(keys))

    def test_состав_приёмов_не_меняется_от_добора(self, family_with_pool):
        """Салат добирается только в обед и ужин: в завтраке ему не место."""
        family, member = family_with_pool

        _, items = generate(family, member, meal_plan_type="3")

        breakfast_roles = {it["component_role"] for it in items if it["meal_slot"] == "breakfast"}
        assert "salad" not in breakfast_roles
