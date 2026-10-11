"""MG_KBJUMATCH: подсказать КБЖУ из каталога по свободно набранному названию.

Случай с прода, с которого всё началось. Человек завёл свой продукт «фарш
телятина» — запись без КБЖУ. В каталоге при этом лежит «Фарш из телятины»,
220 ккал. Поиск его не показал: `search_regex` требует слова подряд и в том
же порядке, а между ними стоит «из».

Названия в тестах выдуманные там, где это не мешает сути: посевная миграция
заводит каталог продуктов в каждую тестовую базу. Там, где важна именно та
пара с прода, она и берётся — но с `get_or_create`, чтобы не спорить с
посевом.
"""

import pytest
from django.urls import reverse

from apps.family.models import Family
from apps.fridge.kbju_match import content_tokens, match_score, suggest_from_catalog
from apps.fridge.models import Product
from apps.users.models import User


class TestРазборНазвания:
    def test_предлог_выброшен(self):
        assert content_tokens("Фарш из телятины") == content_tokens("фарш телятина")

    def test_порядок_слов_не_важен(self):
        assert content_tokens("телятина фарш") == content_tokens("фарш телятина")

    def test_окончания_не_важны(self):
        assert content_tokens("яйцо куриное") == content_tokens("яйца куриные")

    def test_ё_и_е_одна_буква(self):
        assert content_tokens("Свёкла варёная") == content_tokens("свекла вареная")

    def test_из_одних_предлогов_сравнивать_нечего(self):
        # Пустое множество совпадёт с чем угодно, а значит ни с чем — такое
        # название подсказок не получает.
        assert content_tokens("из и с") == frozenset()
        assert content_tokens("400") == frozenset()

    def test_совпадение_считается_долей_общих_слов(self):
        assert match_score(content_tokens("фарш телятина"), content_tokens("Фарш из телятины")) == 1.0
        # Фарш куриный — другой продукт, и подставлять его КБЖУ нельзя.
        assert match_score(content_tokens("фарш телятина"), content_tokens("Фарш куриный")) < 0.5

    def test_пустому_сравниваться_не_с_чем(self):
        assert match_score(frozenset(), content_tokens("фарш")) == 0.0


def _catalog(name, kcal=None, nutrition=None):
    return Product.objects.create(
        name=name,
        source=Product.Source.MANUAL,
        calories_per_100g=kcal,
        nutrition=nutrition or {},
    )


@pytest.mark.django_db
class TestПодсказкаИзКаталога:
    def test_случай_с_прода_фарш_телятина(self):
        target, _ = Product.objects.get_or_create(
            name="Фарш из телятины",
            owner_family=None,
            defaults={
                "source": Product.Source.MANUAL,
                "calories_per_100g": 220,
                "nutrition": {"proteins": 18.3, "fats": 18.4, "carbs": 0.0},
            },
        )

        found = suggest_from_catalog("фарш телятина")

        assert found, "каталожный «Фарш из телятины» должен находиться по «фарш телятина»"
        assert found[0][0].id == target.id
        assert found[0][1] == 1.0

    def test_другой_продукт_не_предлагается(self):
        _catalog("Плюмбус куриный", kcal=143, nutrition={"proteins": 18.2})

        assert suggest_from_catalog("плюмбус телячий") == []

    def test_без_кбжу_предлагать_нечего(self):
        # Подсказка нужна ради чисел; запись без чисел предложить нечего.
        _catalog("Квазибрикус молотый")

        assert suggest_from_catalog("квазибрикус молотый") == []

    def test_короткое_имя_вперёд_при_равном_совпадении(self):
        long_one = _catalog("Квазибрикус охлаждённый, 400г", kcal=200, nutrition={"proteins": 10})
        short_one = _catalog("Квазибрикус охлаждённый", kcal=200, nutrition={"proteins": 10})

        found = suggest_from_catalog("квазибрикус охлажденный 400г")
        ids = [p.id for p, _ in found]

        assert ids[0] == short_one.id
        assert long_one.id in ids

    def test_личные_продукты_в_подсказки_не_идут(self):
        # Каталог общий для всех. Чужая «Мамина настойка» в подсказке у
        # соседа — это утечка, а не помощь.
        user = User.objects.create_user(email="m@example.com", password="x", name="M")
        family = Family.objects.create(name="Семья", owner=user)
        Product.objects.create(
            name="Квазибрикус мамин",
            source=Product.Source.MANUAL,
            owner_family=family,
            calories_per_100g=150,
            nutrition={"proteins": 5},
        )

        assert suggest_from_catalog("квазибрикус мамин") == []

    def test_пустое_название_не_ломает(self):
        assert suggest_from_catalog("") == []
        assert suggest_from_catalog("   ") == []


def _user(email="k@example.com"):
    """Пользователь с премиумом: холодильник без него закрыт даже на чтение."""
    import datetime

    from django.utils import timezone

    from apps.family.models import FamilyMember
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    user = User.objects.create_user(email=email, password="x", name="K")
    family = Family.objects.create(name="Семья", owner=user)
    FamilyMember.objects.create(family=family, user=user, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": "0", "period": "month"}
    )
    Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return user


def _client(user):
    from rest_framework.test import APIClient

    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
class TestРучкаПодсказки:
    def test_отдаёт_подходящее_с_мерой_совпадения(self):
        Product.objects.get_or_create(
            name="Фарш из телятины",
            owner_family=None,
            defaults={
                "source": Product.Source.MANUAL,
                "calories_per_100g": 220,
                "nutrition": {"proteins": 18.3, "fats": 18.4, "carbs": 0.0},
            },
        )

        r = _client(_user()).get(reverse("product-kbju-suggest"), {"name": "фарш телятина"})

        assert r.status_code == 200
        top = r.data["suggestions"][0]
        assert top["name"] == "Фарш из телятины"
        assert top["calories_per_100g"] == "220.00"
        # Меру совпадения клиент получает намеренно: по ней он решает,
        # подставлять кнопкой или сперва показать, что именно предлагается.
        assert top["match"] == 1.0

    def test_короткий_запрос_подсказок_не_получает(self):
        r = _client(_user()).get(reverse("product-kbju-suggest"), {"name": "ф"})

        assert r.status_code == 200
        assert r.data["suggestions"] == []

    def test_гостю_не_отвечаем(self):
        from rest_framework.test import APIClient

        r = APIClient().get(reverse("product-kbju-suggest"), {"name": "фарш телятина"})

        assert r.status_code in (401, 403)


@pytest.mark.django_db
class TestСвоиБезКбжу:
    def test_отбираются_только_свои_и_только_пустые(self):
        user = _user("mine@example.com")
        family = Family.objects.get(owner=user)
        empty = Product.objects.create(name="Квазибрикус мой пустой", source="manual", owner_family=family)
        Product.objects.create(
            name="Квазибрикус мой полный",
            source="manual",
            owner_family=family,
            calories_per_100g=100,
            nutrition={"proteins": 1},
        )
        # Каталожный без КБЖУ — не мой, в этот список попадать не должен.
        Product.objects.create(name="Квазибрикус ничей", source="manual")

        r = _client(user).get(reverse("product-list"), {"own": "1", "no_kbju": "1"})

        assert r.status_code == 200
        assert [p["id"] for p in r.data] == [empty.id]
