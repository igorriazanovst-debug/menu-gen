"""MG_SHELFLIFE: срок годности подставляется при переносе покупок в холодильник.

Раньше товар из списка ложился в холодильник без срока — и напоминание «скоро
испортится» молчало для всего, что куплено, а не вписано руками.

Считаем от даты покупки: даты производства мы не знаем. Поэтому в справочнике
лежит «сколько живёт после покупки», а не срок с этикетки, из которого пришлось
бы вычитать догадку о времени в пути — разную для молока и для крупы.

Подставленная дата — предположение: она видна в окне переноса и правится до
сохранения. Молча проставленный неверный срок родит ложные «испортится», а от
них перестают читать и настоящие.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product, ProductCategory
from apps.fridge.shelf_life import shelf_life_days, suggest_expiry
from apps.shopping.models import ShoppingList, ShoppingListItem
from apps.users.models import User


@pytest.fixture
def dairy(db):
    cat, _ = ProductCategory.objects.get_or_create(
        slug="dairy", defaults={"name_ru": "Молочные продукты"}
    )
    cat.shelf_life_days = 5
    cat.save(update_fields=["shelf_life_days"])
    return cat


@pytest.fixture
def family(db):
    head = User.objects.create_user(email="head@example.com", name="Глава", password="pass12345")
    fam = Family.objects.create(owner=head, name="Семья")
    FamilyMember.objects.create(family=fam, user=head, role=FamilyMember.Role.HEAD)
    return fam, head


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def purchased(family, name="Молоко", **kwargs):
    sl = ShoppingList.objects.create(family=family, name="Закупка")
    item = ShoppingListItem.objects.create(
        shopping_list=sl, name=name, quantity=1, unit="шт", is_purchased=True, **kwargs
    )
    return sl, item


@pytest.mark.django_db
class TestShelfLifeLookup:
    def test_срок_берётся_из_категории(self, dairy):
        assert shelf_life_days(category=dairy) == 5

    def test_срок_продукта_важнее_категории(self, dairy):
        """Ультрапастеризованное молоко живёт полгода — категория этого не знает."""
        p = Product.objects.create(name="Молоко ультрапастеризованное", category_fk=dairy, shelf_life_days=180)

        assert shelf_life_days(product=p) == 180

    def test_без_своего_срока_продукт_наследует_категорию(self, dairy):
        p = Product.objects.create(name="Молоко", category_fk=dairy)

        assert shelf_life_days(product=p) == 5

    def test_неизвестный_срок_не_выдумывается(self, db):
        # Категорию заводит миграция — берём её, а не создаём вторую.
        cat, _ = ProductCategory.objects.get_or_create(slug="household", defaults={"name_ru": "Бытовая химия"})
        cat.shelf_life_days = None
        cat.save(update_fields=["shelf_life_days"])
        p = Product.objects.create(name="Порошок", category_fk=cat)

        assert shelf_life_days(product=p) is None
        assert suggest_expiry(product=p) is None

    def test_дата_считается_от_покупки(self, dairy):
        bought = date(2027, 1, 3)

        assert suggest_expiry(category=dairy, purchased_on=bought) == date(2027, 1, 8)


@pytest.mark.django_db
class TestTransfer:
    def test_срок_подставляется_при_переносе(self, family, dairy):
        fam, head = family
        product = Product.objects.create(name="Молоко", category_fk=dairy)
        sl, _ = purchased(fam, product=product, category_fk=dairy)

        r = api(head).post(reverse("shopping-add-to-fridge", args=[sl.id]), {}, format="json")

        assert r.status_code == 200, r.data
        assert FridgeItem.objects.get(family=fam).expiry_date == date.today() + timedelta(days=5)

    def test_явная_дата_важнее_подстановки(self, family, dairy):
        fam, head = family
        sl, item = purchased(fam, category_fk=dairy)
        mine = str(date.today() + timedelta(days=2))

        api(head).post(
            reverse("shopping-add-to-fridge", args=[sl.id]), {"expiry": {str(item.id): mine}}, format="json"
        )

        assert str(FridgeItem.objects.get(family=fam).expiry_date) == mine

    def test_пустая_дата_у_позиции_отменяет_подстановку(self, family, dairy):
        """Явное «без срока» должно значить именно это, а не «подставь сам»."""
        fam, head = family
        sl, item = purchased(fam, category_fk=dairy)

        api(head).post(
            reverse("shopping-add-to-fridge", args=[sl.id]), {"expiry": {str(item.id): None}}, format="json"
        )

        assert FridgeItem.objects.get(family=fam).expiry_date is None

    def test_семья_может_отключить_подстановку(self, family, dairy):
        fam, head = family
        fam.auto_expiry = False
        fam.save(update_fields=["auto_expiry"])
        sl, _ = purchased(fam, category_fk=dairy)

        api(head).post(reverse("shopping-add-to-fridge", args=[sl.id]), {}, format="json")

        assert FridgeItem.objects.get(family=fam).expiry_date is None

    def test_без_справочного_срока_поле_остаётся_пустым(self, family, db):
        fam, head = family
        cat, _ = ProductCategory.objects.get_or_create(slug="unknown-cat", defaults={"name_ru": "Без срока"})
        sl, _ = purchased(fam, category_fk=cat)

        api(head).post(reverse("shopping-add-to-fridge", args=[sl.id]), {}, format="json")

        assert FridgeItem.objects.get(family=fam).expiry_date is None


@pytest.mark.django_db
class TestSuggestionInApi:
    def test_позиция_списка_отдаёт_предполагаемый_срок(self, family, dairy):
        """Дата нужна фронту до переноса: её показывают и дают поправить."""
        fam, head = family
        sl, _ = purchased(fam, category_fk=dairy)

        r = api(head).get(reverse("shopping-list-detail", args=[sl.id]))

        assert r.status_code == 200, r.data
        assert r.data["items"][0]["suggested_expiry"] == str(date.today() + timedelta(days=5))

    def test_настройка_видна_в_семье(self, family):
        fam, head = family

        r = api(head).get(reverse("family-detail"))

        assert r.data["auto_expiry"] is True

    def test_настройку_можно_выключить(self, family):
        fam, head = family

        r = api(head).patch(reverse("family-detail"), {"auto_expiry": False}, format="json")

        assert r.status_code == 200, r.data
        fam.refresh_from_db()
        assert fam.auto_expiry is False
