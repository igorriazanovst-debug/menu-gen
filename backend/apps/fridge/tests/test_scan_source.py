"""MG_SCANSRC: происхождение записи, созданной сканом штрих-кода.

Раньше скан клал продукт в общий каталог независимо от того, откуда взялись
данные. Для находки в OpenFoodFacts это нормально: штрих-код глобальный, база
открытая, запись проверяема. Но когда OFF товара не знает, продукт «опознаёт»
модель по коду — и такая догадка попадала в тот же каталог, где её видели все
и принимали за справочную. Именно так каталог зарастал безымянными продуктами.

Теперь происхождение записано, и непроверяемая запись не показывается там, где
продукт выбирают (дневник, покупки, конструктор меню). Из базы она при этом не
исчезает: позиция холодильника ссылается на неё, а повторный скан того же кода
должен находить её, а не ходить в сеть заново.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product
from apps.fridge.visibility import catalog_q, visible_products_q
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

OFF_HIT = {
    "status": 1,
    "product": {
        "product_name_ru": "Хлеб бородинский",
        "categories": "Хлеб, выпечка",
        "nutriments": {"energy-kcal_100g": 250, "proteins_100g": 8, "fat_100g": 1.5, "carbohydrates_100g": 50},
    },
}
AI_GUESS = {
    # Имя нарочно небывалое: в каталоге и так есть «Печенье овсяное» из сидов,
    # и по нему было бы не отличить нашу запись от справочной.
    "name": "Батончик протеиновый Челленджер",
    "category": "",
    "default_unit": "",
    "calories_per_100g": 430.0,
    "nutrition": {"proteins": 6.0, "fats": 15.0, "carbs": 68.0},
    "image_url": None,
}


@pytest.fixture
def user(db):
    u = User.objects.create_user(email="scan@example.com", password="pass12345", name="Скан")
    fam = Family.objects.create(name="Семья", owner=u)
    FamilyMember.objects.create(family=fam, user=u, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": "0", "period": "month"}
    )
    import datetime

    from django.utils import timezone

    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return u


def api(u):
    c = APIClient()
    c.force_authenticate(u)
    return c


def off_response(payload):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = payload
    return m


def scan(u, barcode):
    return api(u).post(reverse("fridge-scan"), {"barcode": barcode}, format="json")


def found(u, q):
    """Имена в поиске продуктов (ответ пагинирован)."""
    data = api(u).get(reverse("product-search"), {"q": q}).data
    rows = data["results"] if isinstance(data, dict) else data
    return [p["name"] for p in rows]


@pytest.mark.django_db
class TestOffHit:
    @patch("apps.fridge.services.requests.get")
    def test_находка_в_off_помечена_как_проверяемая(self, mock_get, user):
        mock_get.return_value = off_response(OFF_HIT)

        r = scan(user, "4607000000001")

        assert r.status_code == 200, r.data
        assert Product.objects.get(barcode="4607000000001").source == Product.Source.OFF
        assert r.data["low_confidence"] is False

    @patch("apps.fridge.services.requests.get")
    def test_находка_из_off_остаётся_в_общем_каталоге(self, mock_get, user):
        """Штрих-код один на всех — от такой записи выигрывают все семьи."""
        mock_get.return_value = off_response(OFF_HIT)
        scan(user, "4607000000001")

        assert found(user, "бородинский") == ["Хлеб бородинский"]


@pytest.mark.django_db
class TestAiGuess:
    @patch("apps.fridge.services.gpt_lookup_by_barcode", return_value=dict(AI_GUESS))
    @patch("apps.fridge.services.requests.get")
    def test_догадка_модели_помечена_и_отдана_с_оговоркой(self, mock_get, _gpt, user):
        mock_get.return_value = off_response({"status": 0})

        r = scan(user, "4600000000002")

        assert r.status_code == 200, r.data
        assert r.data["source"] == "ai"
        assert r.data["low_confidence"] is True
        assert Product.objects.get(barcode="4600000000002").source == Product.Source.AI

    @patch("apps.fridge.services.gpt_lookup_by_barcode", return_value=dict(AI_GUESS))
    @patch("apps.fridge.services.requests.get")
    def test_догадка_не_попадает_в_поиск_продуктов(self, mock_get, _gpt, user):
        """В дневнике и покупках её приняли бы за справочную запись."""
        mock_get.return_value = off_response({"status": 0})
        scan(user, "4600000000002")

        assert found(user, "челленджер") == []

    @patch("apps.fridge.services.gpt_lookup_by_barcode", return_value=dict(AI_GUESS))
    @patch("apps.fridge.services.requests.get")
    def test_догадка_не_видна_ни_как_каталог_ни_как_продукт_семьи(self, mock_get, _gpt, user):
        mock_get.return_value = off_response({"status": 0})
        scan(user, "4600000000002")

        assert not Product.objects.filter(catalog_q(), barcode="4600000000002").exists()
        assert not Product.objects.filter(visible_products_q(user), barcode="4600000000002").exists()

    @patch("apps.fridge.services.gpt_lookup_by_barcode", return_value=dict(AI_GUESS))
    @patch("apps.fridge.services.requests.get")
    def test_повторный_скан_находит_её_локально_и_не_идёт_в_сеть(self, mock_get, _gpt, user):
        """Иначе каждый скан этого кода снова дёргал бы OFF и модель."""
        mock_get.return_value = off_response({"status": 0})
        scan(user, "4600000000002")
        calls_before = mock_get.call_count

        r = scan(user, "4600000000002")

        assert r.status_code == 200
        assert r.data["source"] == "local"
        assert r.data["low_confidence"] is True
        assert mock_get.call_count == calls_before

    @patch("apps.fridge.services.gpt_lookup_by_barcode", return_value=dict(AI_GUESS))
    @patch("apps.fridge.services.requests.get")
    def test_кбжу_видно_в_позиции_холодильника(self, mock_get, _gpt, user):
        """Скрыта она только от списков выбора — своей позицией пользоваться можно."""
        mock_get.return_value = off_response({"status": 0})
        product = Product.objects.get(barcode="4600000000002") if scan(user, "4600000000002") else None
        family = user.family_memberships.first().family
        item = FridgeItem.objects.create(family=family, product=product, name=product.name, quantity=1, unit="шт")

        r = api(user).get(reverse("fridge-item-details", args=[item.id]))

        assert r.status_code == 200, r.data
        assert r.data["product"]["calories_per_100g"] == "430.00"


@pytest.mark.django_db
@patch("apps.fridge.services.requests.get")
def test_скан_работает_на_сервере_без_ии_ключа(mock_get, user):
    """Категорию OFF-записи иногда доуточняет модель — и без ключа это падало.

    Ошибка конфигурации ИИ поднималась мимо обработчика (ловился только сбой
    запроса), и скан отвечал пятисоткой там, где достаточно было обойтись без
    подсказки модели.
    """
    mock_get.return_value = off_response(OFF_HIT)

    r = scan(user, "4607000000009")

    assert r.status_code == 200, r.data
    assert r.data["name"] == "Хлеб бородинский"


@pytest.mark.django_db
def test_обычные_продукты_каталога_не_задеты(user):
    """Фильтр по происхождению прячет только догадки, а не всё подряд."""
    Product.objects.create(name="Пробникус ручной", source=Product.Source.MANUAL)
    Product.objects.create(name="Пробникус из рецепта", source=Product.Source.AUTO)
    Product.objects.create(name="Пробникус импортный", source=Product.Source.IMPORT)

    assert found(user, "пробникус") == ["Пробникус из рецепта", "Пробникус импортный", "Пробникус ручной"]
