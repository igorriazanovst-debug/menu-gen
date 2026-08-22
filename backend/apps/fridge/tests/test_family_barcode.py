"""MG_FAMBARCODE: семья запоминает свои штрих-коды.

Справочник сети знает её ассортимент, OpenFoodFacts — то, что попало в открытую
базу. Остальное человек вбивал руками каждый раз заново: код нигде не оставался,
и та же упаковка завтра снова «не найдена».

Отдельная таблица, а не продукт со штрих-кодом: `Product.barcode` уникален на
всю базу, и запись одной семьи заняла бы код у всех остальных — а «Сметана 20%»
у соседей вполне может быть другой марки.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FamilyBarcode, Product, ProductCategory
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

CODE = "4680019310016"  # сметана, которой нет ни в справочнике, ни в OFF


def make_family(email, name="Семья"):
    user = User.objects.create_user(email=email, password="pass12345", name=email.split("@")[0])
    family = Family.objects.create(name=name, owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": "0", "period": "month"}
    )
    import datetime

    from django.utils import timezone

    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return family, user


@pytest.fixture
def ours(db):
    return make_family("ours@example.com", "Наша семья")


@pytest.fixture
def neighbours(db):
    return make_family("neighbours@example.com", "Соседи")


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def scan(user, code=CODE):
    return api(user).post(reverse("fridge-scan"), {"barcode": code}, format="json")


def add_item(user, **payload):
    return api(user).post(reverse("fridge-list"), payload, format="json")


@pytest.mark.django_db
class TestRemember:
    @patch("apps.fridge.services.requests.get")
    def test_ручной_ввод_после_неудачного_скана_запоминается(self, mock_get, ours):
        family, user = ours

        add_item(user, name="Сметана Коровка из Кореновки 20%", quantity=1, unit="шт", barcode=CODE)

        entry = FamilyBarcode.objects.get(family=family)
        assert entry.name == "Сметана Коровка из Кореновки 20%"
        assert entry.unit == "шт"

    @patch("apps.fridge.services.requests.get")
    def test_запомненное_подставляется_при_следующем_скане(self, mock_get, ours):
        """Ради этого всё и затевалось: второй раз вводить не нужно."""
        family, user = ours
        add_item(user, name="Сметана Коровка из Кореновки 20%", quantity=1, unit="шт", barcode=CODE)

        r = scan(user)

        assert r.status_code == 200, r.data
        assert r.data["name"] == "Сметана Коровка из Кореновки 20%"
        assert r.data["source"] == "family"
        assert r.data["default_unit"] == "шт"
        assert mock_get.call_count == 0

    @patch("apps.fridge.services.requests.get")
    def test_категория_тоже_запоминается(self, mock_get, ours, db):
        family, user = ours
        ProductCategory.objects.get_or_create(slug="dairy", defaults={"name_ru": "Молочные продукты"})

        add_item(user, name="Сметана", quantity=1, unit="шт", barcode=CODE, category_slug="dairy")

        assert scan(user).data["category_slug"] == "dairy"

    @patch("apps.fridge.services.requests.get")
    def test_повторный_ввод_обновляет_а_не_плодит(self, mock_get, ours):
        family, user = ours
        add_item(user, name="Сметана", quantity=1, unit="шт", barcode=CODE)

        add_item(user, name="Сметана Коровка 20%", quantity=1, unit="шт", barcode=CODE)

        assert FamilyBarcode.objects.filter(family=family).count() == 1
        assert scan(user).data["name"] == "Сметана Коровка 20%"

    @patch("apps.fridge.services.requests.get")
    def test_код_в_другом_написании_это_тот_же_код(self, mock_get, ours):
        family, user = ours
        add_item(user, name="Соус", quantity=1, unit="шт", barcode="011210000032")

        assert scan(user, "0011210000032").data["name"] == "Соус"

    @patch("apps.fridge.services.requests.get")
    def test_без_кода_ничего_не_запоминается(self, mock_get, ours):
        family, user = ours

        add_item(user, name="Сметана", quantity=1, unit="шт")

        assert FamilyBarcode.objects.count() == 0


@pytest.mark.django_db
class TestScope:
    @patch("apps.fridge.services.requests.get")
    def test_соседи_нашей_памяти_не_видят(self, mock_get, ours, neighbours):
        """«Сметана 20%» у соседей вполне может быть другой марки."""
        _, our_user = ours
        _, their_user = neighbours
        add_item(our_user, name="Сметана Коровка из Кореновки 20%", quantity=1, unit="шт", barcode=CODE)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0}
        mock_get.return_value = mock_resp

        r = scan(their_user)

        assert r.status_code == 404

    @patch("apps.fridge.services.requests.get")
    def test_один_код_у_двух_семей_живёт_независимо(self, mock_get, ours, neighbours):
        """Ровно то, ради чего заведена отдельная таблица: barcode у продукта уникален."""
        _, our_user = ours
        _, their_user = neighbours

        add_item(our_user, name="Сметана Коровка", quantity=1, unit="шт", barcode=CODE)
        add_item(their_user, name="Сметана Домик в деревне", quantity=1, unit="шт", barcode=CODE)

        assert scan(our_user).data["name"] == "Сметана Коровка"
        assert scan(their_user).data["name"] == "Сметана Домик в деревне"

    @patch("apps.fridge.services.requests.get")
    def test_память_семьи_важнее_справочника(self, mock_get, ours):
        """Если код попал и туда, и туда, — своё название семьи главнее.

        Так бывает, когда товар сперва завели руками, а позже он появился в
        очередной выгрузке: подменять уже привычное название не надо.
        """
        family, user = ours
        Product.objects.create(name="Сметана какая-то, 500г", barcode=CODE, source=Product.Source.RETAIL)
        FamilyBarcode.objects.create(family=family, barcode=CODE, name="Сметана Коровка из Кореновки 20%")

        assert scan(user).data["name"] == "Сметана Коровка из Кореновки 20%"

    @patch("apps.fridge.services.requests.get")
    def test_опознанный_товар_память_не_засоряет(self, mock_get, ours):
        """Запоминать нечего: справочник и так знает этот код."""
        family, user = ours
        product = Product.objects.create(name="Сметана из справочника", barcode=CODE, source=Product.Source.RETAIL)

        add_item(user, name="Сметана", quantity=1, unit="шт", barcode=CODE, product=product.id)

        assert FamilyBarcode.objects.count() == 0
