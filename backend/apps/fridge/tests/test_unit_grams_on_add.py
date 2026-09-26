"""MG_FAMWEIGHT: человек сам говорит, сколько граммов в его упаковке.

Справочник закрывает товары со штрихкодом. Обобщённые записи каталога —
«Творог 5%», к которому привязаны рецепты, — он закрыть не может: пачки у всех
разные. Единственный, кто знает вес своей пачки, — тот, кто её принёс.

Поэтому форма добавления спрашивает вес, и ответ запоминается за семьёй. С
этого момента её холодильник сходится с рецептами сам, без разовых заливок.

Спрашивать надо не всегда: у граммов и килограммов вес известен из арифметики,
и лишняя строка в справочнике только собьёт с толку. Это проверяется отдельно.

Названия выдуманы: посевная миграция заводит каталог в каждую тестовую базу.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family
from apps.fridge.models import FridgeItem, Product, ProductUnitWeight
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner(db):
    user = User.objects.create_user(email="addweight@example.com", password="pass12345", name="Хозяин")
    _bootstrap_user(user)
    return user


@pytest.fixture
def family(owner, grant_premium):
    family = Family.objects.get(owner=owner)
    grant_premium(family)
    return family


@pytest.fixture
def curd(db):
    return Product.objects.create(name="Творог плюмбусный")


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _add(client, product, unit, **extra):
    payload = {
        "product": product.id,
        "name": product.name,
        "quantity": "2",
        "unit": unit,
        "expiry_date": "2027-01-01",
        **extra,
    }
    return client.post("/api/v1/fridge/", payload, format="json")


@pytest.mark.django_db
class TestВесПриДобавлении:
    def test_ответ_человека_запоминается_за_семьёй(self, owner, family, curd):
        resp = _add(_client(owner), curd, "упаковка", unit_grams="400")

        assert resp.status_code == 201
        row = ProductUnitWeight.objects.get(product=curd, unit="упаковка")
        assert row.grams == Decimal("400.00")
        assert row.family_id == family.id
        assert row.source == ProductUnitWeight.Source.MANUAL

    def test_общий_каталог_не_трогается(self, owner, family, curd):
        """Своя пачка — своё дело. Соседям её вес доставаться не должен."""
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))

        _add(_client(owner), curd, "упаковка", unit_grams="400")

        common = ProductUnitWeight.objects.get(product=curd, unit="упаковка", family__isnull=True)
        assert common.grams == Decimal("200.00")

    def test_после_добавления_позиция_сходится_с_рецептом(self, owner, family, curd):
        """Ради этого всё и делалось."""
        from apps.fridge.units import to_grams

        _add(_client(owner), curd, "упаковка", unit_grams="400")

        assert to_grams(Decimal("2"), "упаковка", curd.id, family=family) == Decimal("800.00")

    def test_без_ответа_ничего_не_пишется(self, owner, family, curd):
        _add(_client(owner), curd, "упаковка")

        assert not ProductUnitWeight.objects.filter(product=curd).exists()

    def test_у_граммов_вес_не_спрашивается(self, owner, family, curd):
        """Единица уже мера — запись была бы мусором в справочнике."""
        _add(_client(owner), curd, "г", unit_grams="400")

        assert not ProductUnitWeight.objects.filter(product=curd).exists()

    def test_у_литров_тоже_не_пишется(self, owner, family, curd):
        _add(_client(owner), curd, "л", unit_grams="1030")

        assert not ProductUnitWeight.objects.filter(product=curd).exists()

    def test_ноль_и_минус_не_принимаются(self, owner, family, curd):
        for bad in ("0", "-100"):
            resp = _add(_client(owner), curd, "упаковка", unit_grams=bad)
            assert resp.status_code == 400, bad

        assert not ProductUnitWeight.objects.filter(product=curd).exists()

    def test_позиция_без_товара_вес_не_запоминает(self, owner, family):
        """Привязать вес не к чему: справочник ведётся по товару."""
        client = _client(owner)
        resp = client.post(
            "/api/v1/fridge/",
            {"name": "Нечто безымянное", "quantity": "1", "unit": "упаковка", "expiry_date": "2027-01-01"},
            format="json",
        )

        assert resp.status_code == 201
        assert ProductUnitWeight.objects.count() == 0

    def test_повторный_ответ_обновляет_свой_вес(self, owner, family, curd):
        """Человек передумал или ошибся — последнее сказанное вернее."""
        client = _client(owner)
        _add(client, curd, "упаковка", unit_grams="400")

        _add(client, curd, "упаковка", unit_grams="180")

        row = ProductUnitWeight.objects.get(product=curd, unit="упаковка", family=family)
        assert row.grams == Decimal("180.00")


@pytest.mark.django_db
class TestВесПриПравке:
    def test_правка_позиции_задаёт_вес(self, owner, family, curd):
        item = FridgeItem.objects.create(
            family=family, product=curd, name=curd.name, quantity=Decimal("1"), unit="упаковка"
        )

        resp = _client(owner).patch(f"/api/v1/fridge/{item.id}/", {"unit_grams": "350"}, format="json")

        assert resp.status_code == 200
        assert ProductUnitWeight.objects.get(product=curd, family=family).grams == Decimal("350.00")


@pytest.mark.django_db
class TestПодсказкаВФорме:
    def test_товар_отдаёт_известные_веса(self, owner, family, curd):
        """Форме есть чем предзаполнить поле — человек не вводит вслепую."""
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))

        resp = _client(owner).get(f"/api/v1/fridge/products/search/?q={curd.name}")

        found = next(p for p in resp.data["results"] if p["id"] == curd.id)
        assert found["unit_weights"] == {"упаковка": "200.00"}

    def test_свой_вес_показывается_вместо_общего(self, owner, family, curd):
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("200"))
        ProductUnitWeight.objects.create(product=curd, unit="упаковка", grams=Decimal("400"), family=family)

        resp = _client(owner).get(f"/api/v1/fridge/products/search/?q={curd.name}")

        found = next(p for p in resp.data["results"] if p["id"] == curd.id)
        assert found["unit_weights"] == {"упаковка": "400.00"}
