"""MG_MEALSLOT: у записи дневника есть точное место в дне, а не только род еды.

Зачем понадобилось. `meal_type` отвечает на вопрос «какого рода эта еда» — по
нему подбираются рецепты и работает запрет на сладкое в основных приёмах.
Перекус там один, и для подбора это правильно: первый и второй ничем не
отличаются. А человеку в дневнике при пяти приёмах в день нужны два перекуса
раздельно — они в разное время и с разной едой.

Поэтому раскладка дня — отдельное поле, ровно как у позиции меню
(`MenuItem.meal_slot`), откуда слот и приходит при заполнении дневника из меню.

Главное, что здесь проверяется, — эти два поля не могут разойтись. Дважды в
проекте разметка расходилась с раскладкой (T-21, T-22), и оба раза это стоило
недостижимых рецептов; здесь согласование сделано в модели, а не в каждой ручке.

Названия выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не дневники.
"""

from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.users.models import User


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pwd12345!")


def _family(owner, name):
    family = Family.objects.create(owner=owner, name=name)
    member = FamilyMember.objects.create(family=family, user=owner, role=FamilyMember.Role.HEAD)
    return family, member


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def person(db):
    user = _user("edok@example.test", "Едок")
    _family(user, "Семья Едока")
    return user


# ── слот и род еды не расходятся ─────────────────────────────────────────────


@pytest.mark.django_db
def test_slot_defines_the_meal_type(person):
    entry = DiaryEntry.objects.create(
        user=person,
        date=date.today(),
        meal_slot=DiaryEntry.MealSlot.SNACK2,
        custom_name="Яблоко проверочное",
        nutrition={},
        quantity=1,
    )
    assert entry.meal_type == DiaryEntry.MealType.SNACK


@pytest.mark.django_db
def test_meal_type_alone_gets_a_default_slot(person):
    """Старый клиент шлёт только род еды — слот проставится сам."""
    entry = DiaryEntry.objects.create(
        user=person,
        date=date.today(),
        meal_type=DiaryEntry.MealType.SNACK,
        custom_name="Орехи проверочные",
        nutrition={},
        quantity=1,
    )
    # Какой это был перекус, не знает никто: до сих пор это нигде не хранилось.
    assert entry.meal_slot == DiaryEntry.MealSlot.SNACK1


@pytest.mark.django_db
def test_contradiction_is_resolved_in_favour_of_the_slot(person):
    """Если прислали и то и другое, и они спорят — слот главнее.

    Слот точнее: из него род еды выводится однозначно, а обратно — нет.
    """
    entry = DiaryEntry.objects.create(
        user=person,
        date=date.today(),
        meal_type=DiaryEntry.MealType.DINNER,
        meal_slot=DiaryEntry.MealSlot.LUNCH,
        custom_name="Спорное проверочное",
        nutrition={},
        quantity=1,
    )
    assert entry.meal_type == DiaryEntry.MealType.LUNCH


@pytest.mark.django_db
def test_every_slot_maps_to_a_real_meal_type():
    """Таблица соответствия покрывает все слоты и не выдумывает родов еды."""
    slots = {s.value for s in DiaryEntry.MealSlot}
    assert set(DiaryEntry.SLOT_TO_MEAL_TYPE) == slots
    meal_types = {m.value for m in DiaryEntry.MealType}
    assert set(DiaryEntry.SLOT_TO_MEAL_TYPE.values()) <= meal_types
    assert set(DiaryEntry.MEAL_TYPE_TO_SLOT) == meal_types
    assert set(DiaryEntry.MEAL_TYPE_TO_SLOT.values()) <= slots


# ── через API ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_api_accepts_and_returns_the_slot(client, person):
    client.force_authenticate(person)
    resp = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "snack2",
            "custom_name": "Творог проверочный",
            "nutrition": {"calories": {"value": 120}},
            "quantity": 1,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["meal_slot"] == "snack2"
    assert resp.data["meal_type"] == "snack"

    listed = client.get(reverse("diary-list"), {"date": str(date.today())})
    assert [row["meal_slot"] for row in listed.data["results"]] == ["snack2"]


@pytest.mark.django_db
def test_old_client_without_slot_still_works(client, person):
    """Приложения 1.0.5 и 1.0.7 про слот не знают и шлют только род еды."""
    client.force_authenticate(person)
    resp = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_type": "snack",
            "custom_name": "Банан проверочный",
            "nutrition": {},
            "quantity": 1,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["meal_slot"] == "snack1"


@pytest.mark.django_db
def test_entry_can_be_moved_between_snacks(client, person):
    """Первый перекус угадан по умолчанию — человек должен мочь поправить."""
    client.force_authenticate(person)
    created = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_type": "snack",
            "custom_name": "Переносимое проверочное",
            "nutrition": {},
            "quantity": 1,
        },
        format="json",
    ).data
    assert created["meal_slot"] == "snack1"

    resp = client.patch(
        reverse("diary-entry-detail", args=[created["id"]]),
        {"meal_slot": "snack2"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["meal_slot"] == "snack2"
    assert resp.data["meal_type"] == "snack"


# ── план дня раскладывается по двум перекусам ────────────────────────────────


@pytest.mark.django_db
def test_import_from_menu_keeps_the_two_snacks_apart(client, person):
    """Ровно то, ради чего слот и заводился.

    В меню на пять приёмов перекусов два, и в позициях меню они различены с
    самого начала. Дневник этого не забирал — оба сваливались в один «Перекус».
    """
    from apps.menu.models import Menu, MenuItem
    from apps.recipes.models import Recipe

    family = Family.objects.get(owner=person)
    member = FamilyMember.objects.get(user=person)
    # creator_id — обычное число, а не связь: так заведено в модели меню.
    menu = Menu.objects.create(family=family, creator_id=person.id, start_date=date.today(), end_date=date.today())
    first = Recipe.objects.create(title="Первый перекус проверочный", is_published=True, nutrition={})
    second = Recipe.objects.create(title="Второй перекус проверочный", is_published=True, nutrition={})
    MenuItem.objects.create(menu=menu, recipe=first, member=member, meal_type="snack", meal_slot="snack1", day_offset=0)
    MenuItem.objects.create(
        menu=menu, recipe=second, member=member, meal_type="snack", meal_slot="snack2", day_offset=0
    )

    client.force_authenticate(person)
    resp = client.post(
        f"{reverse('diary-import-from-menu')}?menu_id={menu.id}&date={date.today()}",
        {},
        format="json",
    )
    assert resp.status_code == 200
    slots = {row["recipe_title"]: row["meal_slot"] for row in resp.data["entries"]}
    assert slots == {
        "Первый перекус проверочный": "snack1",
        "Второй перекус проверочный": "snack2",
    }


@pytest.mark.django_db
def test_copying_a_day_keeps_the_slot(client, person):
    from datetime import timedelta

    client.force_authenticate(person)
    created = client.post(
        reverse("diary-list"),
        {
            "date": str(date.today()),
            "meal_slot": "snack2",
            "custom_name": "Копируемое проверочное",
            "nutrition": {},
            "quantity": 1,
        },
        format="json",
    ).data

    tomorrow = date.today() + timedelta(days=1)
    resp = client.post(
        reverse("diary-copy"),
        {"entry_ids": [created["id"]], "target_date": str(tomorrow)},
        format="json",
    )
    assert resp.status_code == 201
    assert [row["meal_slot"] for row in resp.data] == ["snack2"]
