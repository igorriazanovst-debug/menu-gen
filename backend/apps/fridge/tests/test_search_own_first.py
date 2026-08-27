"""MG_OWNFIRST: продукт, заведённый пользователем, должен находиться поиском.

Жалоба звучала так: «добавил блюдо в дневник вручную, в каталоге продуктов оно
появляется, а в поиске для повторного добавления — нет».

Причина оказалась не в видимости, а в сортировке. Поиск отдаёт двадцать записей,
отсортированных по названию, и продукт семьи стоял в этой очереди наравне с
каталожными: по частому слову («рыба», «сыр») каталог даёт двадцать совпадений
раньше, чем очередь дойдёт до своего. На экране «Мои продукты» он при этом
виден — там отбор по семье и без среза.

Поэтому свои идут первыми. Ниже проверяется и это, и то, что общий каталог из
выдачи никуда не делся, и что приоритет не приоткрывает чужое.
"""

import pytest
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import Product
from apps.users.models import User

URL = "/api/v1/fridge/products/search/"


@pytest.fixture
def семья(db):
    owner = User.objects.create_user(email="u@example.com", password="pass12345", name="У")
    family = Family.objects.create(name="Семья", owner=owner)
    FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return owner, family


@pytest.fixture
def клиент(семья):
    owner, _family = семья
    c = APIClient()
    c.force_authenticate(owner)
    return c


def названия(response):
    assert response.status_code == 200, (response.status_code, response.json())
    payload = response.json()
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    return [row["name"] for row in rows]


@pytest.mark.django_db
class TestСвоиПервыми:
    def test_свой_продукт_не_теряется_среди_каталожных(self, семья, клиент):
        """Ровно тот случай из жалобы: каталог забивает всю выдачу."""
        _owner, family = семья
        for i in range(25):
            Product.objects.create(name="Рыба каталожная %02d" % i, source=Product.Source.MANUAL)
        свой = Product.objects.create(name="Рыба масляная копчёная", owner_family=family)

        assert свой.name in названия(клиент.get(URL, {"q": "рыба"}))

    def test_свой_продукт_стоит_первым(self, семья, клиент):
        """Его заводили руками — значит он и нужен, а не двадцать каталожных."""
        _owner, family = семья
        Product.objects.create(name="Аварийный каталожный сыр", source=Product.Source.MANUAL)
        Product.objects.create(name="Ярославский сыр", owner_family=family)

        assert названия(клиент.get(URL, {"q": "сыр"}))[0] == "Ярославский сыр"

    def test_каталог_по_прежнему_ищется(self, клиент):
        Product.objects.create(name="Гречка ядрица", source=Product.Source.MANUAL)

        assert "Гречка ядрица" in названия(клиент.get(URL, {"q": "ядрица"}))

    def test_чужой_семейный_продукт_не_виден(self, клиент, db):
        """Своё — своей семье. Приоритет не должен приоткрывать чужое."""
        чужак = User.objects.create_user(email="o@example.com", password="pass12345", name="Ч")
        чужая = Family.objects.create(name="Чужие", owner=чужак)
        Product.objects.create(name="Чужая аджика", owner_family=чужая)

        assert названия(клиент.get(URL, {"q": "аджика"})) == []

    def test_короткий_запрос_не_ищем(self, клиент):
        Product.objects.create(name="Сыр", source=Product.Source.MANUAL)

        assert названия(клиент.get(URL, {"q": "с"})) == []
