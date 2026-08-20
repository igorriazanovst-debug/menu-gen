"""MG_PRODFAMILY: общий каталог неизменен, свои товары — только своей семье.

Что было до этого (проверено экспериментом на текущем коде):

- товар, вписанный руками в список покупок, создавался БЕЗ владельца, то есть
  попадал в общий каталог и находился поиском у всех — в проде так туда попали
  «прокладки Белла ночные» и «блоки для туалета»;
- личный продукт одной семьи находился в рубрикаторе списка покупок у чужих:
  фильтр видимости стоял только в эндпоинтах холодильника;
- позиция чужого списка молча привязывалась к личному продукту другой семьи
  (совпадение по имени искалось по всей таблице) вместе с его категорией,
  единицей и последней ценой;
- продукт был личным для ПОЛЬЗОВАТЕЛЯ: второй взрослый в той же семье его
  не видел, хотя список покупок они ведут вместе.

Здесь проверяется правило целиком: каталог виден всем и не растёт от ввода,
продукт семьи виден всей семье и только ей.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.models import Product, ProductCategory
from apps.shopping.models import ShoppingList, ShoppingListItem
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def category(db):
    cat, _ = ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее"})
    return cat


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


def make_family(tag, members=1):
    head = User.objects.create_user(email=f"{tag}@example.com", name=tag, password="pass12345")
    family = Family.objects.create(owner=head, name=f"Семья {tag}")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    premium(family)
    users = [head]
    for i in range(members - 1):
        u = User.objects.create_user(email=f"{tag}{i}@example.com", name=f"{tag}{i}", password="pass12345")
        FamilyMember.objects.create(family=family, user=u, role=FamilyMember.Role.MEMBER)
        users.append(u)
    return family, users


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def add_item(user, shopping_list, name, category_slug="other"):
    return api(user).post(
        f"/api/v1/shopping/lists/{shopping_list.id}/items/",
        {"name": name, "quantity": 1, "unit": "шт", "category_slug": category_slug},
        format="json",
    )


@pytest.mark.django_db
class TestCatalogStaysShared:
    def test_товар_из_списка_покупок_не_попадает_в_каталог(self, category):
        """Главное: пользовательский ввод больше не пополняет общий справочник."""
        fam, (head,) = make_family("a")
        sl = ShoppingList.objects.create(family=fam, name="Список")

        r = add_item(head, sl, "Прокладки ночные")

        assert r.status_code == 201, r.data
        p = Product.objects.get(name="Прокладки ночные")
        assert p.owner_family_id == fam.id, "продукт остался в общем каталоге"

    def test_чужой_не_видит_этот_товар_в_поиске(self, category):
        fam_a, (a,) = make_family("a")
        fam_b, (b,) = make_family("b")
        sl = ShoppingList.objects.create(family=fam_a, name="Список")
        add_item(a, sl, "Прокладки ночные")

        r = api(b).get("/api/v1/shopping/rubric/search/", {"q": "Прокладки"})

        assert r.status_code == 200
        assert r.data["results"] == []

    def test_чужой_не_видит_товар_при_просмотре_категории(self, category):
        fam_a, (a,) = make_family("a")
        fam_b, (b,) = make_family("b")
        sl = ShoppingList.objects.create(family=fam_a, name="Список")
        add_item(a, sl, "Мамина настойка")

        r = api(b).get("/api/v1/shopping/rubric/browse/", {"category": "other"})

        assert "Мамина настойка" not in [x["name"] for x in r.data["results"]]

    def test_каталожный_продукт_виден_всем(self, category):
        """Обратная сторона: общий каталог остаётся общим."""
        Product.objects.create(name="Кефирный напиток каталожный", category_fk=category, is_seed=True)
        _, (a,) = make_family("a")
        _, (b,) = make_family("b")

        for user in (a, b):
            r = api(user).get("/api/v1/shopping/rubric/search/", {"q": "Кефирный напиток каталожный"})
            assert [x["name"] for x in r.data["results"]] == ["Кефирный напиток каталожный"]

    def test_чужой_ввод_не_привязывается_к_продукту_другой_семьи(self, category):
        """Совпадение по имени искалось по всей таблице — и находило чужое."""
        fam_a, (a,) = make_family("a")
        fam_b, (b,) = make_family("b")
        sl_a = ShoppingList.objects.create(family=fam_a, name="Список A")
        add_item(a, sl_a, "Мамина настойка")
        product_a = Product.objects.get(name="Мамина настойка", owner_family=fam_a)

        sl_b = ShoppingList.objects.create(family=fam_b, name="Список B")
        add_item(b, sl_b, "Мамина настойка")

        item_b = ShoppingListItem.objects.get(shopping_list=sl_b)
        assert item_b.product_id != product_a.id
        assert Product.objects.get(id=item_b.product_id).owner_family_id == fam_b.id

    def test_нельзя_привязаться_к_чужому_продукту_по_id(self, category):
        """Фильтр списка не спасает, если id передан напрямую."""
        fam_a, (a,) = make_family("a")
        fam_b, (b,) = make_family("b")
        sl_a = ShoppingList.objects.create(family=fam_a, name="Список A")
        add_item(a, sl_a, "Мамина настойка")
        alien = Product.objects.get(name="Мамина настойка", owner_family=fam_a)

        sl_b = ShoppingList.objects.create(family=fam_b, name="Список B")
        r = api(b).post(
            f"/api/v1/shopping/lists/{sl_b.id}/items/",
            {
                "name": "Мамина настойка",
                "quantity": 1,
                "unit": "шт",
                "category_slug": "other",
                "product_id": alien.id,
            },
            format="json",
        )

        assert r.status_code == 201, r.data
        assert ShoppingListItem.objects.get(shopping_list=sl_b).product_id != alien.id


@pytest.mark.django_db
class TestFamilyScope:
    def test_второй_взрослый_видит_продукт_семьи(self, category):
        """Ради этого владельцем сделана семья, а не пользователь."""
        fam, (head, spouse) = make_family("a", members=2)
        sl = ShoppingList.objects.create(family=fam, name="Список")
        add_item(head, sl, "Мамина настойка")

        r = api(spouse).get("/api/v1/shopping/rubric/search/", {"q": "Мамина"})

        assert [x["name"] for x in r.data["results"]] == ["Мамина настойка"]

    def test_второй_взрослый_видит_продукт_в_справочнике_холодильника(self, category):
        fam, (head, spouse) = make_family("a", members=2)
        api(head).post(
            "/api/v1/fridge/products/",
            {"name": "Мамина настойка", "category_id": category.id},
            format="json",
        )

        r = api(spouse).get("/api/v1/fridge/products/")

        assert "Мамина настойка" in [x["name"] for x in r.data]

    def test_чужой_не_видит_его_в_справочнике_холодильника(self, category):
        fam_a, (a,) = make_family("a")
        _, (b,) = make_family("b")
        api(a).post(
            "/api/v1/fridge/products/",
            {"name": "Мамина настойка", "category_id": category.id},
            format="json",
        )

        r = api(b).get("/api/v1/fridge/products/")

        assert "Мамина настойка" not in [x["name"] for x in r.data]

    def test_второй_взрослый_может_править_продукт_семьи(self, category):
        """Опечатку исправляет любой из семьи, не только автор."""
        fam, (head, spouse) = make_family("a", members=2)
        r = api(head).post(
            "/api/v1/fridge/products/",
            {"name": "Мамина настойкa", "category_id": category.id},
            format="json",
        )
        pid = r.data["id"]

        r2 = api(spouse).patch(f"/api/v1/fridge/products/{pid}/", {"name": "Мамина настойка"}, format="json")

        assert r2.status_code == 200, r2.data
        assert Product.objects.get(id=pid).name == "Мамина настойка"

    def test_каталожный_продукт_не_правится_из_приложения(self, category):
        """Общий список неизменен — правки только через админку."""
        catalog = Product.objects.create(name="Кефирный напиток каталожный", category_fk=category, is_seed=True)
        _, (a,) = make_family("a")

        r = api(a).patch(f"/api/v1/fridge/products/{catalog.id}/", {"name": "Моё"}, format="json")

        assert r.status_code == 403
        assert Product.objects.get(id=catalog.id).name == "Кефирный напиток каталожный"

    def test_чужой_продукт_недоступен_по_прямому_адресу(self, category):
        fam_a, (a,) = make_family("a")
        _, (b,) = make_family("b")
        r = api(a).post(
            "/api/v1/fridge/products/",
            {"name": "Мамина настойка", "category_id": category.id},
            format="json",
        )
        pid = r.data["id"]

        assert api(b).get(f"/api/v1/fridge/products/{pid}/").status_code == 404
        assert api(b).delete(f"/api/v1/fridge/products/{pid}/").status_code == 404
        assert Product.objects.filter(id=pid).exists()


@pytest.mark.django_db
class TestOwnerComesFromList:
    def test_админ_добавляет_в_чужой_список_товар_достаётся_семье_списка(self, category):
        """Владелец берётся из списка, а не из того, кто добавляет.

        Обычный член семьи позиций не добавляет (это право главы семьи), но
        админ добавляет в любой список — и вписанное им должно принадлежать
        хозяевам списка, а не уезжать в его собственный справочник.
        """
        fam_a, (a,) = make_family("a")
        admin = User.objects.create_user(
            email="admin@example.com", name="Админ", password="pass12345", user_type="admin"
        )
        fam_admin, _ = make_family("adm")
        FamilyMember.objects.create(family=fam_admin, user=admin, role=FamilyMember.Role.MEMBER)
        sl = ShoppingList.objects.create(family=fam_a, name="Список A")

        r = add_item(admin, sl, "Гостевой товар")

        assert r.status_code == 201, r.data
        assert Product.objects.get(name="Гостевой товар").owner_family_id == fam_a.id


@pytest.mark.django_db
class TestDataMigration:
    """Перенос старых данных: логика миграции 0017, вызванная напрямую.

    Проверяется на настоящем реестре моделей — сама миграция берёт их через
    apps.get_model, так что поведение то же.
    """

    def test_перенос(self, category):
        import importlib

        module = importlib.import_module("apps.fridge.migrations.0017_products_to_families")
        from django.apps import apps as real_apps

        fam_a, (a,) = make_family("a")
        fam_b, (b,) = make_family("b")

        # 1) продукт с владельцем-пользователем → семье этого пользователя
        by_owner = Product.objects.create(name="Старый личный", category_fk=category, owner=a)

        # 2) ничей продукт, но в списке ровно одной семьи → этой семье
        from_list = Product.objects.create(name="Прокладки ночные", category_fk=category)
        sl_a = ShoppingList.objects.create(family=fam_a, name="Список A")
        ShoppingListItem.objects.create(shopping_list=sl_a, name="Прокладки ночные", product=from_list)

        # 3) ничей продукт в списках РАЗНЫХ семей → владельца не угадать, остаётся в каталоге
        ambiguous = Product.objects.create(name="Хлеб белый", category_fk=category)
        sl_b = ShoppingList.objects.create(family=fam_b, name="Список B")
        ShoppingListItem.objects.create(shopping_list=sl_a, name="Хлеб белый", product=ambiguous)
        ShoppingListItem.objects.create(shopping_list=sl_b, name="Хлеб белый", product=ambiguous)

        # 4) seed-каталог не трогаем, даже если он попал в чей-то список
        seed = Product.objects.create(name="Молоко каталожное", category_fk=category, is_seed=True)
        ShoppingListItem.objects.create(shopping_list=sl_a, name="Молоко каталожное", product=seed)

        module.to_families(real_apps, None)

        assert Product.objects.get(id=by_owner.id).owner_family_id == fam_a.id
        assert Product.objects.get(id=from_list.id).owner_family_id == fam_a.id
        assert Product.objects.get(id=ambiguous.id).owner_family_id is None
        assert Product.objects.get(id=seed.id).owner_family_id is None

    def test_повторный_запуск_ничего_не_ломает(self, category):
        import importlib

        module = importlib.import_module("apps.fridge.migrations.0017_products_to_families")
        from django.apps import apps as real_apps

        fam, (head,) = make_family("a")
        p = Product.objects.create(name="Старый личный", category_fk=category, owner=head)

        module.to_families(real_apps, None)
        module.to_families(real_apps, None)

        assert Product.objects.get(id=p.id).owner_family_id == fam.id
