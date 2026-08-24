"""MG_MYPRODUCTS: своими продуктами можно управлять.

Заводить продукты семьи стало легко (галочка в дневнике включена по умолчанию),
а управлять ими было негде: бэкенд правку и удаление умел, но фронт про них не
знал — ни списка, ни кнопок. Экран «Мои продукты» это закрыл, и держаться он
должен на трёх вещах:

- список отдаёт ТОЛЬКО продукты своей семьи (каталог туда не течёт);
- вместе с ними приходит счётчик позиций холодильника — без него нельзя честно
  предупредить перед удалением;
- каталожный продукт правке и удалению не поддаётся, чем бы его ни просили.

Отдельно проверяется, что позиция холодильника переживает удаление продукта:
FK стоит SET_NULL, и потерять содержимое холодильника из-за чистки справочника
было бы худшим из возможных сюрпризов.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem, Product, ProductCategory
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

PRODUCTS_URL = "/api/v1/fridge/products/"


@pytest.fixture
def category(db):
    cat, _ = ProductCategory.objects.get_or_create(slug="fish", defaults={"name_ru": "Рыба"})
    return cat


def make_family(tag):
    head = User.objects.create_user(email=f"{tag}@example.com", name=tag, password="pass12345")
    family = Family.objects.create(owner=head, name=f"Семья {tag}")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
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
    return family, head


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
class TestOwnProductsList:
    def test_список_своих_не_содержит_каталог(self, category):
        fam, head = make_family("own")
        Product.objects.create(name="Масляная рыба копчёная", owner_family=fam, category_fk=category)
        Product.objects.create(name="Треска каталожная", owner_family=None, category_fk=category)

        r = api(head).get(PRODUCTS_URL, {"own": "1"})

        assert r.status_code == 200, r.data
        names = [p["name"] for p in r.data]
        assert "Масляная рыба копчёная" in names
        assert "Треска каталожная" not in names

    def test_чужие_продукты_не_видны(self, category):
        fam_a, head_a = make_family("a")
        fam_b, _ = make_family("b")
        Product.objects.create(name="Рыба соседа", owner_family=fam_b, category_fk=category)

        r = api(head_a).get(PRODUCTS_URL, {"own": "1"})

        assert [p["name"] for p in r.data] == []

    def test_счётчик_позиций_холодильника_приходит(self, category):
        """Без него предупреждение перед удалением было бы враньём наугад."""
        fam, head = make_family("cnt")
        product = Product.objects.create(name="Рыба учтённая", owner_family=fam, category_fk=category)
        for i in range(2):
            FridgeItem.objects.create(family=fam, product=product, name=f"Рыба {i}", quantity=1, unit="шт")

        r = api(head).get(PRODUCTS_URL, {"own": "1"})

        assert r.data[0]["fridge_usage"] == 2


@pytest.mark.django_db
class TestEditAndDelete:
    def test_свой_продукт_правится(self, category):
        fam, head = make_family("edit")
        p = Product.objects.create(name="Рыба с опечаткй", owner_family=fam)

        r = api(head).patch(
            f"{PRODUCTS_URL}{p.id}/",
            {"name": "Рыба масляная", "calories_per_100g": 180, "category_id": category.id},
            format="json",
        )

        assert r.status_code == 200, r.data
        p.refresh_from_db()
        assert p.name == "Рыба масляная"
        assert float(p.calories_per_100g) == 180
        assert p.category_fk_id == category.id

    def test_свой_продукт_удаляется(self):
        fam, head = make_family("del")
        p = Product.objects.create(name="Лишний продукт", owner_family=fam)

        r = api(head).delete(f"{PRODUCTS_URL}{p.id}/")

        assert r.status_code == 204
        assert not Product.objects.filter(id=p.id).exists()

    def test_позиция_холодильника_переживает_удаление_продукта(self):
        """Чистка справочника не должна выносить содержимое холодильника."""
        fam, head = make_family("keep")
        p = Product.objects.create(name="Рыба привязанная", owner_family=fam)
        item = FridgeItem.objects.create(family=fam, product=p, name="Рыба", quantity=1, unit="шт")

        api(head).delete(f"{PRODUCTS_URL}{p.id}/")

        item.refresh_from_db()
        assert item.product_id is None
        assert item.name == "Рыба"

    def test_каталожный_продукт_править_нельзя(self, category):
        fam, head = make_family("cat")
        p = Product.objects.create(name="Треска общая", owner_family=None, category_fk=category)

        r = api(head).patch(f"{PRODUCTS_URL}{p.id}/", {"name": "Моя треска"}, format="json")

        assert r.status_code == 403, r.data
        p.refresh_from_db()
        assert p.name == "Треска общая"

    def test_каталожный_продукт_удалить_нельзя(self, category):
        fam, head = make_family("catdel")
        p = Product.objects.create(name="Треска неприкосновенная", owner_family=None, category_fk=category)

        r = api(head).delete(f"{PRODUCTS_URL}{p.id}/")

        assert r.status_code == 403
        assert Product.objects.filter(id=p.id).exists()

    def test_чужой_продукт_править_нельзя(self):
        fam_a, head_a = make_family("x")
        fam_b, _ = make_family("y")
        p = Product.objects.create(name="Продукт соседа", owner_family=fam_b)

        r = api(head_a).patch(f"{PRODUCTS_URL}{p.id}/", {"name": "Теперь мой"}, format="json")

        assert r.status_code in (403, 404), r.data
        p.refresh_from_db()
        assert p.name == "Продукт соседа"
