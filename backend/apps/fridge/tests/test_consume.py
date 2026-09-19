"""MG_WRITEOFF: ручное списание позиции холодильника («израсходовал»).

Отдельно от списания по блюду, потому что правила другие: блюдо знает, сколько
ему нужно, и считает это в граммах, а здесь человек смотрит на конкретную пачку
и говорит, сколько ушло из НЕЁ. Переводить единицы незачем — перевод
(MG_UNITNORM) нужен там, где встречаются рецепт и холодильник, а тут правда
одна.

Названия выдуманы: посевная миграция заводит каталог в каждую тестовую базу.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family
from apps.fridge.models import FridgeItem, FridgeWriteOff, Product
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def owner(db):
    user = User.objects.create_user(email="consume@example.com", password="pass12345", name="Хозяин")
    _bootstrap_user(user)
    return user


@pytest.fixture
def family(owner, grant_premium):
    family = Family.objects.get(owner=owner)
    # Холодильник на запись закрыт премиумом — как и всё остальное в нём.
    grant_premium(family)
    return family


@pytest.fixture
def item(family):
    product = Product.objects.create(name="Плюмбус мясной")
    return FridgeItem.objects.create(
        family=family, product=product, name=product.name, quantity=Decimal("500"), unit="г"
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestИзрасходовал:
    def test_часть_уходит_остаток_остаётся(self, owner, item):
        resp = _client(owner).post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "200"}, format="json")

        assert resp.status_code == 200
        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")
        assert item.is_deleted is False

    def test_без_количества_уходит_всё(self, owner, item):
        """Чаще всего именно так: пачку доели."""
        resp = _client(owner).post(f"/api/v1/fridge/{item.id}/consume/", {}, format="json")

        assert resp.status_code == 200
        item.refresh_from_db()
        assert item.quantity == Decimal("0.00")
        assert item.is_deleted is True

    def test_больше_чем_лежит_списать_нельзя(self, owner, item):
        """Остаток обрезается: холодильник не уходит в минус."""
        _client(owner).post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "900"}, format="json")

        item.refresh_from_db()
        assert item.quantity == Decimal("0.00")
        assert item.is_deleted is True
        line = FridgeWriteOff.objects.get().lines.get()
        assert line.quantity == Decimal("500.00")

    def test_ноль_и_минус_не_принимаются(self, owner, item):
        for bad in ("0", "-5"):
            resp = _client(owner).post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": bad}, format="json")
            assert resp.status_code == 400, bad

        item.refresh_from_db()
        assert item.quantity == Decimal("500.00")

    def test_списание_записывается_как_ручное(self, owner, item):
        resp = _client(owner).post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "200"}, format="json")

        write_off = FridgeWriteOff.objects.get(id=resp.data["write_off_id"])
        assert write_off.reason == FridgeWriteOff.Reason.MANUAL
        assert write_off.menu_id is None
        line = write_off.lines.get()
        assert line.quantity == Decimal("200.00")
        assert line.unit == "г"

    def test_единица_позиции_сохраняется(self, owner, family):
        """Яйца лежат в штуках — в штуках и списываются.

        Даже когда вес штуки известен: перевод здесь не нужен, а округление
        при нём стоило бы точности.
        """
        eggs = Product.objects.create(name="Яйцо плюмбусиное")
        row = FridgeItem.objects.create(family=family, product=eggs, name=eggs.name, quantity=Decimal("10"), unit="шт")

        _client(owner).post(f"/api/v1/fridge/{row.id}/consume/", {"quantity": "3"}, format="json")

        row.refresh_from_db()
        assert row.quantity == Decimal("7.00")
        assert row.unit == "шт"

    def test_чужую_позицию_не_тронуть(self, item, grant_premium):
        # Премиум чужому тоже выдаём: иначе его остановит платный гейт, и тест
        # будет проверять подписку вместо того, ради чего написан, — границы
        # чужого холодильника.
        stranger = User.objects.create_user(email="stranger2@example.com", password="pass12345", name="Чужой")
        _bootstrap_user(stranger)
        grant_premium(Family.objects.get(owner=stranger))

        resp = _client(stranger).post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "100"}, format="json")

        assert resp.status_code == 404
        item.refresh_from_db()
        assert item.quantity == Decimal("500.00")


@pytest.mark.django_db
class TestОтменаСписания:
    def test_возвращает_ровно_то_что_ушло(self, owner, item):
        client = _client(owner)
        resp = client.post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "200"}, format="json")

        undo = client.delete(f"/api/v1/fridge/write-offs/{resp.data['write_off_id']}/")

        assert undo.status_code == 204
        item.refresh_from_db()
        assert item.quantity == Decimal("500.00")
        assert FridgeWriteOff.objects.count() == 0

    def test_позиция_ушедшая_в_ноль_возвращается(self, owner, item):
        client = _client(owner)
        resp = client.post(f"/api/v1/fridge/{item.id}/consume/", {}, format="json")

        client.delete(f"/api/v1/fridge/write-offs/{resp.data['write_off_id']}/")

        item.refresh_from_db()
        assert item.quantity == Decimal("500.00")
        assert item.is_deleted is False

    def test_повторная_отмена_не_ошибка(self, owner, item):
        client = _client(owner)
        resp = client.post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "200"}, format="json")
        wid = resp.data["write_off_id"]
        client.delete(f"/api/v1/fridge/write-offs/{wid}/")

        again = client.delete(f"/api/v1/fridge/write-offs/{wid}/")

        assert again.status_code == 204
        item.refresh_from_db()
        assert item.quantity == Decimal("500.00")

    def test_чужое_списание_не_отменить(self, owner, item, grant_premium):
        client = _client(owner)
        resp = client.post(f"/api/v1/fridge/{item.id}/consume/", {"quantity": "200"}, format="json")
        stranger = User.objects.create_user(email="stranger3@example.com", password="pass12345", name="Чужой")
        _bootstrap_user(stranger)
        grant_premium(Family.objects.get(owner=stranger))

        _client(stranger).delete(f"/api/v1/fridge/write-offs/{resp.data['write_off_id']}/")

        item.refresh_from_db()
        assert item.quantity == Decimal("300.00")
        assert FridgeWriteOff.objects.count() == 1
