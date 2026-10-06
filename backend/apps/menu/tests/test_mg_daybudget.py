"""MG_DAYBUDGET: дневные правила генератора должны считаться там, где пишутся.

Три жалобы с прода оказались одним корнем, и это стоит записать: в режиме
«одно меню на всю семью» подбор спрашивает счётчики дня у виртуального члена
(`member_id=0`), а записываются они каждому НАСТОЯЩЕМУ члену. Виртуальный
остаётся с нулями навсегда, и все дневные правила разом перестают работать:

* лимит «не больше одного десерта с выпечкой в сутки» не срабатывает — в обеде
  оказываются и десерт, и выпечка, что человек читает как «два десерта»;
* правило «хотя бы один растительный белок в день» срабатывает ВСЕГДА, потому
  что ноль всегда меньше единицы, — и каждое основное блюдо каждого обеда и
  ужина становится бобовым;
* лимит масла в сутки не срабатывает тоже.

Отдельно проверяется, что растительный белок не забирает себе обед. Правило
дневное, слотов с основным блюдом в дне два, и выполнять его надо в последнем —
иначе обед остаётся без мяса каждый день, даже когда счётчики считаются верно.

Названия выдуманы: посевная миграция заводит каталог продуктов в каждую
тестовую базу.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.family.models import Family, FamilyMember
from apps.menu.generator import DESSERT_MAX_PER_DAY, MenuGenerator
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import Profile, User


def _recipe(title, dish_type, *, protein_type=None, calories=300, **extra):
    return Recipe.objects.create(
        title=title,
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "Шаг"}],
        nutrition={
            "calories": {"value": str(calories), "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats": {"value": "5", "unit": "г"},
            "carbs": {"value": "30", "unit": "г"},
            "weight": {"value": "200", "unit": "г"},
        },
        categories=[],
        is_published=True,
        dish_type=dish_type,
        protein_type=protein_type,
        suitable_for=["breakfast", "lunch", "dinner", "snack"],
        **extra,
    )


def _premium(family):
    """Премиум нужен, иначе семья больше одного человека не соберётся."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": Decimal("0")}
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - datetime.timedelta(days=1),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )


def _family(n_members, email_tag):
    """Семья из n человек. Два и больше — чтобы включился режим family."""
    owner = User.objects.create_user(email=f"{email_tag}-0@example.com", name="Глава", password="pass12345")
    Profile.objects.create(user=owner, birth_year=1985, calorie_target=2400)
    family = Family.objects.create(owner=owner, name="Семья")
    _premium(family)
    members = [FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)]
    for i in range(1, n_members):
        user = User.objects.create_user(email=f"{email_tag}-{i}@example.com", name=f"Член {i}", password="pass12345")
        Profile.objects.create(user=user, birth_year=1990, calorie_target=2000)
        members.append(FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.MEMBER))
    return family, members


def _seed_full_pool(*, plant_mains=8, animal_mains=8, sweets=6):
    """Пул, в котором у генератора есть ВЫБОР.

    Это важно: при пустом пуле правила не отличить от нехватки рецептов, и тест
    показывал бы зелёный на сломанном коде.
    """
    for i in range(animal_mains):
        _recipe(f"Курица плюмбусная {i}", "main", protein_type="animal", food_group="protein")
    for i in range(plant_mains):
        _recipe(f"Фасоль плюмбусная {i}", "main", protein_type="plant", food_group="protein")
    for i in range(6):
        _recipe(f"Завтрак плюмбусный {i}", "breakfast_dish", food_group="grain")
        _recipe(f"Салат плюмбусный {i}", "salad", food_group="vegetable")
        _recipe(f"Суп плюмбусный {i}", "soup", food_group="vegetable")
    for i in range(sweets):
        _recipe(f"Десерт плюмбусный {i}", "dessert", food_group="dairy")
        _recipe(f"Выпечка плюмбусная {i}", "bakery", food_group="grain")


def _generate(family, members, *, days=2, mode="family"):
    gen = MenuGenerator(
        family=family,
        members=members,
        period_days=days,
        start_date=datetime.date.today(),
        plan_code="premium",
        filters={"mode": mode, "meal_plan_type": "3"},
    )
    return gen.generate()


def _by_slot(items, member_id, day, slot):
    return [i for i in items if i["member"].id == member_id and i["day_offset"] == day and i["meal_slot"] == slot]


@pytest.mark.django_db
class TestСладкоеВОбеде:
    def test_в_обеде_не_больше_одного_сладкого(self):
        """Десерт и выпечка — два разных слота обеда, но одно ограничение.

        Человек видит в обеде два сладких блюда и называет это «два десерта».
        """
        family, members = _family(3, "daybudget-sweet")
        _seed_full_pool()

        items = _generate(family, members, days=2)

        for day in (0, 1):
            lunch = _by_slot(items, members[0].id, day, "lunch")
            sweet = [i for i in lunch if i["component_role"] in ("dessert", "bakery")]
            assert len(sweet) <= DESSERT_MAX_PER_DAY, [i["recipe"].title for i in sweet]


@pytest.mark.django_db
class TestРастительныйБелок:
    def test_обед_не_обязан_быть_бобовым(self):
        """Правило дневное — выполнять его должен ужин, а не обед.

        До починки обед получал растительное основное блюдо каждый день: на
        момент подбора обеда счётчик дня равен нулю, ноль меньше единицы, и
        кандидаты сужались до бобовых. Человеку это видно как «обед без мяса»
        и «опять фасоль».

        Пул намеренно перекошен, и числа подобраны прогонами, а не на глаз —
        менять их, не перепроверив обе стороны, не стоит.

        Снизу их держит сломанный код: он обязан падать КАЖДЫЙ раз. Бобовых
        должно быть заметно больше, чем дней, потому что ужин тоже берёт их
        себе. На пуле «бобовых ровно по числу дней» сломанный код ловился лишь
        в двух прогонах из пяти: пары блюд не хватало, последний обед доставался
        мясному, и тест зеленел на сломанном генераторе.

        Сверху их держит исправный код: когда правило обед не держит, блюдо
        берётся из пула случайно (`random.choice`). На ровном пуле 8/8 за три
        дня все три обеда оказывались бобовыми примерно в одном прогоне из
        восьми — так тест и упал в CI на коммите, который питона не касался.
        При мясных вдесятеро больше бобовых такое совпадение на пяти днях —
        примерно раз на триста тысяч прогонов.
        """
        family, members = _family(3, "daybudget-plant-lunch")
        _seed_full_pool(plant_mains=10, animal_mains=100)

        items = _generate(family, members, days=5)

        lunch_mains = [
            i
            for i in items
            if i["member"].id == members[0].id and i["meal_slot"] == "lunch" and i["component_role"] == "main"
        ]
        assert lunch_mains, "в обеде должно быть основное блюдо"
        assert any(i["recipe"].protein_type != "plant" for i in lunch_mains), [i["recipe"].title for i in lunch_mains]

    def test_растительный_белок_в_дне_всё_же_есть(self):
        """Починка не должна отменить само правило: один раз в день — нужен."""
        family, members = _family(3, "daybudget-plant-day")
        _seed_full_pool()

        items = _generate(family, members, days=3)

        for day in range(3):
            day_items = [i for i in items if i["member"].id == members[0].id and i["day_offset"] == day]
            assert any(i["recipe"].protein_type == "plant" for i in day_items), [
                (i["meal_slot"], i["recipe"].title) for i in day_items
            ]


@pytest.mark.django_db
class TestОдноБлюдоДваждыВПриёме:
    def test_в_одном_приёме_не_повторяется_одно_блюдо(self):
        """Запасной путь подбора разрешает уже использованные рецепты.

        Это терпимо на другой день и недопустимо в одном приёме: веб-карточка
        склеивает одинаковые блюда в одно, и человек видит обед из двух блюд
        вместо трёх. А когда он заменяет одно из них, второе проявляется — и
        выглядит это как «замена добавила блюдо».

        Пул намеренно мал: иначе запасной путь не включится.
        """
        family, members = _family(3, "daybudget-dup")
        # Одно основное, один салат, один суп — на два дня этого не хватает,
        # и генератор пойдёт по запасному пути.
        _recipe("Единственное горячее плюмбусное", "main", protein_type="animal", food_group="protein")
        _recipe("Единственный салат плюмбусный", "salad", food_group="vegetable")
        _recipe("Единственный суп плюмбусный", "soup", food_group="vegetable")
        _recipe("Единственный завтрак плюмбусный", "breakfast_dish", food_group="grain")

        items = _generate(family, members, days=2)

        for day in (0, 1):
            for slot in ("breakfast", "lunch", "dinner"):
                meal = _by_slot(items, members[0].id, day, slot)
                titles = [i["recipe"].id for i in meal]
                assert len(titles) == len(set(titles)), [i["recipe"].title for i in meal]
