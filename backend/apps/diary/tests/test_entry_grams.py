"""MG_DIARYGRAMS: вес съеденного хранится числом, а не внутри названия.

Зачем понадобилось. Вес попадал в дневник только текстом — «Творог, 120 г», — и
поправить его было нельзя: КБЖУ пересчитать не из чего, а разбирать название
строкой значит гадать («Хлеб, 2 куска, 60 г»). Правка записи из-за этого умела
всё, кроме главного: съел не сто грамм, а сто пятьдесят.

Теперь вес — отдельное необязательное поле. Необязательное потому, что у старых
записей его нет и у порционных («1 порция супа») может не быть; экран в таком
случае просто не предлагает менять вес.

Названия выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не дневники.
"""

from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.users.models import User


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def person(db):
    user = _user("vesovshchik@example.test", "Весовщик")
    family = Family.objects.create(owner=user, name="Семья Весовщика")
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return user


@pytest.mark.django_db
def test_grams_are_saved_and_returned(client, person):
    client.force_authenticate(person)
    resp = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "breakfast",
            "custom_name": "Творог проверочный",
            "nutrition": {"calories": {"value": "120"}},
            "quantity": 1,
            "grams": 150,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["grams"] == 150

    listed = client.get(reverse("diary-list"), {"date": str(date.today())})
    assert [row["grams"] for row in listed.data["results"]] == [150]


@pytest.mark.django_db
def test_weight_can_be_corrected(client, person):
    """Ровно то, ради чего поле заводилось: съел не сто грамм, а сто пятьдесят.

    КБЖУ пересчитывает клиент — он же и показывает человеку, что получилось,
    до сохранения. Сервер принимает и вес, и новые цифры.
    """
    client.force_authenticate(person)
    created = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "lunch",
            "custom_name": "Каша проверочная",
            "nutrition": {"calories": {"value": "100"}},
            "quantity": 1,
            "grams": 100,
        },
        format="json",
    ).data

    resp = client.patch(
        reverse("diary-entry-detail", args=[created["id"]]),
        {"grams": 150, "nutrition": {"calories": {"value": "150"}}},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["grams"] == 150
    assert resp.data["nutrition"]["calories"]["value"] == "150"


@pytest.mark.django_db
def test_entry_without_weight_is_normal(client, person):
    """Порционная запись веса не имеет, и это не ошибка."""
    client.force_authenticate(person)
    resp = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "dinner",
            "custom_name": "Суп проверочный, 1 порция",
            "nutrition": {},
            "quantity": 1,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["grams"] is None


@pytest.mark.django_db
def test_negative_weight_is_rejected(client, person):
    client.force_authenticate(person)
    resp = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "breakfast",
            "custom_name": "Отрицательное проверочное",
            "nutrition": {},
            "quantity": 1,
            "grams": -10,
        },
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_import_from_menu_takes_the_weight_of_a_product_dish(client, person):
    """У позиции-продукта в меню вес известен точно — забираем его."""
    from apps.fridge.models import Product
    from apps.menu.models import Menu, MenuItem

    family = Family.objects.get(owner=person)
    member = FamilyMember.objects.get(user=person)
    menu = Menu.objects.create(family=family, creator_id=person.id, start_date=date.today(), end_date=date.today())
    # Название выдуманное: посевной каталог продуктов в тестовой базе есть, и
    # взять из него настоящее имя значило бы конфликтовать с посевом.
    product = Product.objects.create(name="Йогурт проверочный", calories_per_100g=60)
    MenuItem.objects.create(
        menu=menu,
        product=product,
        member=member,
        meal_type="snack",
        meal_slot="snack1",
        grams=180,
        day_offset=0,
    )

    client.force_authenticate(person)
    resp = client.post(
        f"{reverse('diary-import-from-menu')}?menu_id={menu.id}&date={date.today()}",
        {},
        format="json",
    )
    assert resp.status_code == 200
    assert [row["grams"] for row in resp.data["entries"]] == [180]


@pytest.mark.django_db
def test_copying_a_day_keeps_the_weight(client, person):
    from datetime import timedelta

    client.force_authenticate(person)
    created = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "breakfast",
            "custom_name": "Копируемое проверочное",
            "nutrition": {},
            "quantity": 1,
            "grams": 90,
        },
        format="json",
    ).data

    resp = client.post(
        reverse("diary-copy"),
        {"entry_ids": [created["id"]], "target_date": str(date.today() + timedelta(days=1))},
        format="json",
    )
    assert resp.status_code == 201
    assert [row["grams"] for row in resp.data] == [90]
