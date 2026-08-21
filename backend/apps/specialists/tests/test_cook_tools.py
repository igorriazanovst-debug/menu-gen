"""MG_COOK: инструменты личного повара.

Матрица отдаёт повару меню, холодильник и списки покупок — но весь этот код
писался до того, как повара появились, и опирался на членство в семье. Своей
семьи у специалиста в разговоре с клиентом нет, поэтому роль, которой поручена
закупка, не могла ни завести список, ни открыть холодильник.

Здесь проверяется, что повар делает свою работу целиком, а чужие роли туда
не проходят: тренеру закупка и холодильник закрыты матрицей.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product, ProductCategory
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe, RecipeProduct
from apps.shopping.models import ShoppingList, ShoppingListItem
from apps.specialists.models import Specialist, SpecialistAssignment
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def premium(family):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Премиум", "price": Decimal("500.00"), "period": "month"}
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status="active",
        started_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def client_family(db):
    head = User.objects.create_user(email="client@example.com", name="Клиент", password="pass12345")
    family = Family.objects.create(owner=head, name="Семья клиента")
    member = FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    premium(family)
    return family, head, member


def make_specialist(email, spec_type):
    user = User.objects.create_user(email=email, name=email.split("@")[0], password="pass12345")
    prof = Specialist.objects.create(user=user, specialist_type=spec_type, is_verified=True)
    return user, prof


def assign(prof, family, status=SpecialistAssignment.Status.ACTIVE):
    return SpecialistAssignment.objects.create(
        family=family, specialist=prof, specialist_type=prof.specialist_type, status=status
    )


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def cook(client_family):
    family, _, _ = client_family
    user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
    assign(prof, family)
    return user, prof


@pytest.mark.django_db
class TestShoppingForClient:
    def test_повар_заводит_список_клиенту(self, client_family, cook):
        """Главное: роль, которой поручена закупка, может её начать."""
        family, _, _ = client_family
        cook_user, _ = cook

        r = api(cook_user).post(
            reverse("shopping-lists"), {"name": "Закупка на неделю", "source": "empty"}, format="json"
        )

        assert r.status_code == 201, r.data
        sl = ShoppingList.objects.get()
        assert sl.family_id == family.id, "список должен принадлежать семье клиента"
        assert sl.created_by_id == cook_user.id

    def test_список_клиента_виден_повару(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        ShoppingList.objects.create(family=family, name="Список семьи")

        r = api(cook_user).get(reverse("shopping-lists"))

        assert [x["name"] for x in r.data] == ["Список семьи"]

    def test_повар_правит_позиции_списка(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее"})
        sl = ShoppingList.objects.create(family=family, name="Список")

        r = api(cook_user).post(
            reverse("shopping-items", args=[sl.id]),
            {"name": "Молоко", "quantity": 1, "unit": "шт", "category_slug": "other"},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert ShoppingListItem.objects.filter(shopping_list=sl).count() == 1

    def test_тренеру_закупка_закрыта(self, client_family):
        """У тренера в матрице списков покупок нет вовсе."""
        family, _, _ = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        ShoppingList.objects.create(family=family, name="Список семьи")

        assert api(trainer_user).get(reverse("shopping-lists")).data == []
        r = api(trainer_user).post(reverse("shopping-lists"), {"name": "Свой", "source": "empty"}, format="json")
        assert r.status_code in (400, 403)

    def test_завершённое_назначение_закрывает_доступ(self, client_family):
        family, _, _ = client_family
        cook_user, prof = make_specialist("cook2@example.com", Specialist.Type.COOK)
        assign(prof, family, status=SpecialistAssignment.Status.ENDED)
        ShoppingList.objects.create(family=family, name="Список семьи")

        assert api(cook_user).get(reverse("shopping-lists")).data == []

    def test_чужая_семья_недоступна_даже_по_явному_id(self, client_family, cook):
        cook_user, _ = cook
        stranger = User.objects.create_user(email="s@example.com", name="S", password="pass12345")
        alien = Family.objects.create(owner=stranger, name="Чужая семья")
        FamilyMember.objects.create(family=alien, user=stranger, role=FamilyMember.Role.HEAD)

        r = api(cook_user).post(
            f"{reverse('shopping-lists')}?family_id={alien.id}",
            {"name": "Список", "source": "empty"},
            format="json",
        )

        assert r.status_code == 403
        assert not ShoppingList.objects.filter(family=alien).exists()


@pytest.mark.django_db
class TestFridgeForClient:
    def test_повар_видит_холодильник_клиента(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        FridgeItem.objects.create(family=family, name="Молоко", quantity=1, unit="шт")

        r = api(cook_user).get(reverse("fridge-list"))

        assert r.status_code == 200, r.data
        assert [x["name"] for x in r.data["results"]] == ["Молоко"]

    def test_повар_кладёт_продукт_в_холодильник(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook

        r = api(cook_user).post(
            reverse("fridge-list"), {"name": "Треска", "quantity": 1, "unit": "кг"}, format="json"
        )

        assert r.status_code == 201, r.data
        assert FridgeItem.objects.get(family=family).name == "Треска"

    def test_тренеру_холодильник_закрыт(self, client_family):
        family, _, _ = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        FridgeItem.objects.create(family=family, name="Молоко", quantity=1, unit="шт")

        r = api(trainer_user).get(reverse("fridge-list"))

        assert r.data["results"] == []


@pytest.mark.django_db
class TestExpiryOnTransfer:
    def _list_with_purchase(self, family):
        sl = ShoppingList.objects.create(family=family, name="Закупка")
        item = ShoppingListItem.objects.create(
            shopping_list=sl, name="Треска", quantity=1, unit="кг", is_purchased=True
        )
        return sl, item

    def test_срок_проставляется_на_позицию(self, client_family, cook):
        """Раньше товар ложился без срока — напоминание молчало."""
        family, _, _ = client_family
        cook_user, _ = cook
        sl, item = self._list_with_purchase(family)
        when = str(date.today() + timedelta(days=2))

        r = api(cook_user).post(
            reverse("shopping-add-to-fridge", args=[sl.id]), {"expiry": {str(item.id): when}}, format="json"
        )

        assert r.status_code == 200, r.data
        assert str(FridgeItem.objects.get(family=family).expiry_date) == when

    def test_общий_срок_на_всю_закупку(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        sl, _ = self._list_with_purchase(family)
        when = str(date.today() + timedelta(days=5))

        api(cook_user).post(
            reverse("shopping-add-to-fridge", args=[sl.id]), {"expiry_date": when}, format="json"
        )

        assert str(FridgeItem.objects.get(family=family).expiry_date) == when

    def test_без_срока_как_раньше(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        sl, _ = self._list_with_purchase(family)

        api(cook_user).post(reverse("shopping-add-to-fridge", args=[sl.id]), {}, format="json")

        assert FridgeItem.objects.get(family=family).expiry_date is None

    def test_кривая_дата_отклоняется(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook
        sl, _ = self._list_with_purchase(family)

        r = api(cook_user).post(
            reverse("shopping-add-to-fridge", args=[sl.id]), {"expiry_date": "завтра"}, format="json"
        )

        assert r.status_code == 400
        assert not FridgeItem.objects.filter(family=family).exists()


@pytest.mark.django_db
class TestDayPlan:
    def _menu_with_dish(self, family, member, title="Треска с овощами", day_offset=0):
        recipe = Recipe.objects.create(title=title)
        menu = Menu.objects.create(
            family=family,
            creator_id=member.user_id,
            period_days=7,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
            status=Menu.Status.ACTIVE,
        )
        MenuItem.objects.create(
            menu=menu, recipe=recipe, member=member, meal_type="lunch", meal_slot="lunch", day_offset=day_offset
        )
        return menu, recipe

    def test_блюда_дня_с_порциями(self, client_family, cook):
        """Одно блюдо на двоих — это одно блюдо и две порции, а не два блюда."""
        family, head, member = client_family
        cook_user, _ = cook
        spouse = User.objects.create_user(email="sp@example.com", name="Супруг", password="pass12345")
        member2 = FamilyMember.objects.create(family=family, user=spouse, role=FamilyMember.Role.MEMBER)
        menu, recipe = self._menu_with_dish(family, member)
        MenuItem.objects.create(
            menu=menu, recipe=recipe, member=member2, meal_type="lunch", meal_slot="lunch", day_offset=0
        )

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert r.status_code == 200, r.data
        dishes = r.data["meals"][0]["dishes"]
        assert len(dishes) == 1
        assert dishes[0]["title"] == "Треска с овощами"
        assert dishes[0]["servings"] == 2
        assert sorted(dishes[0]["eaters"]) == ["Клиент", "Супруг"]

    def test_меню_на_всю_семью_считает_порции_по_числу_едоков(self, client_family, cook):
        """Без разбивки по участникам «1 порция» на семью — обман повара."""
        family, head, member = client_family
        cook_user, _ = cook
        spouse = User.objects.create_user(email="sp@example.com", name="Супруг", password="pass12345")
        FamilyMember.objects.create(family=family, user=spouse, role=FamilyMember.Role.MEMBER)
        recipe = Recipe.objects.create(title="Суп")
        menu = Menu.objects.create(
            family=family,
            creator_id=head.id,
            period_days=1,
            start_date=date.today(),
            end_date=date.today(),
            status=Menu.Status.ACTIVE,
        )
        MenuItem.objects.create(menu=menu, recipe=recipe, member=None, meal_type="lunch", day_offset=0)

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert r.data["meals"][0]["dishes"][0]["servings"] == 2

    def test_чего_не_хватает_в_холодильнике(self, client_family, cook):
        family, head, member = client_family
        cook_user, _ = cook
        _, recipe = self._menu_with_dish(family, member)
        cod = Product.objects.create(name="Треска")
        onion = Product.objects.create(name="Лук")
        RecipeProduct.objects.create(recipe=recipe, product=cod, name_raw="треска")
        RecipeProduct.objects.create(recipe=recipe, product=onion, name_raw="лук")
        FridgeItem.objects.create(family=family, product=onion, name="Лук", quantity=1, unit="шт")

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert [m["name"] for m in r.data["missing"]] == ["Треска"]

    def test_скоропортящееся_в_наряде(self, client_family, cook):
        family, _, member = client_family
        cook_user, _ = cook
        self._menu_with_dish(family, member)
        FridgeItem.objects.create(
            family=family, name="Сметана", quantity=1, unit="шт", expiry_date=date.today() + timedelta(days=1)
        )
        FridgeItem.objects.create(
            family=family, name="Крупа", quantity=1, unit="кг", expiry_date=date.today() + timedelta(days=60)
        )

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert [x["name"] for x in r.data["expiring"]] == ["Сметана"]
        assert r.data["expiring"][0]["days_left"] == 1

    def test_день_без_меню_не_ошибка(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert r.status_code == 200
        assert r.data["menu_id"] is None
        assert r.data["meals"] == []

    def test_дата_выбирается_параметром(self, client_family, cook):
        family, _, member = client_family
        cook_user, _ = cook
        self._menu_with_dish(family, member, title="Завтрашнее", day_offset=1)

        today = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]))
        tomorrow = api(cook_user).get(
            reverse("cabinet-client-day-plan", args=[family.id]), {"date": str(date.today() + timedelta(days=1))}
        )

        assert today.data["meals"] == []
        assert tomorrow.data["meals"][0]["dishes"][0]["title"] == "Завтрашнее"

    def test_кривая_дата_отклоняется(self, client_family, cook):
        family, _, _ = client_family
        cook_user, _ = cook

        r = api(cook_user).get(reverse("cabinet-client-day-plan", args=[family.id]), {"date": "вчера"})

        assert r.status_code == 400

    def test_чужому_специалисту_наряд_не_виден(self, client_family):
        family, _, _ = client_family
        other_user, prof = make_specialist("other@example.com", Specialist.Type.COOK)
        # назначения на эту семью нет

        r = api(other_user).get(reverse("cabinet-client-day-plan", args=[family.id]))

        assert r.status_code == 403
