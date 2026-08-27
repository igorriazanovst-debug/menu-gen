"""MG_USERPICK: пользователь в админке выбирается из списка, а не вводится числом.

Жалоба: «при регистрации специалиста поле выбора пользователя — простой текст,
причём потеряны пользователи, которые регистрировались через телефон».

Так выглядит `raw_id_fields`: в поле стоит числовой id, рядом лупа, а кто это —
неизвестно, пока не откроешь. Заменено на `autocomplete_fields` — выпадающий
список с поиском.

Телефонные пользователи находятся потому, что `UserAdmin.search_fields`
включает `phone`. Это и проверяется: у половины наших пользователей e-mail нет
вовсе, и поиск только по нему делает их невидимыми для оператора.
"""

import json

import pytest
from django.contrib import admin

from apps.family.models import Family, FamilyMember
from apps.fridge.models import Product
from apps.notifications.models import Notification
from apps.specialists.models import Specialist
from apps.users.models import User

URL = "/admin/autocomplete/"


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="admin@example.com", password="pass12345", name="Админ", is_staff=True, is_superuser=True
    )


def найденные(client, *, app, model, field, term):
    r = client.get(URL, {"app_label": app, "model_name": model, "field_name": field, "term": term})
    assert r.status_code == 200, r.status_code
    return [row["text"] for row in json.loads(r.content)["results"]]


@pytest.mark.django_db
class TestВыборПользователя:
    def test_телефонный_пользователь_находится(self, client, staff):
        """Половина базы без e-mail — по нему одному их не найти."""
        User.objects.create_user(phone="+79990001122", password="pass12345", name="Пётр Телефонов")
        client.force_login(staff)

        assert найденные(client, app="specialists", model="specialist", field="user", term="79990001122")

    def test_ищется_по_имени(self, client, staff):
        """Оператор знает человека по имени, а не по адресу почты."""
        User.objects.create_user(phone="+79990002233", password="pass12345", name="Мария Иванова")
        client.force_login(staff)

        assert найденные(client, app="specialists", model="specialist", field="user", term="Иванова")

    def test_ищется_по_почте(self, client, staff):
        User.objects.create_user(email="klient@example.com", password="pass12345", name="Клиент")
        client.force_login(staff)

        assert найденные(client, app="specialists", model="specialist", field="user", term="klient@")

    def test_посторонним_закрыто(self, client, db):
        r = client.get(URL, {"app_label": "specialists", "model_name": "specialist", "field_name": "user", "term": "a"})

        assert r.status_code in (302, 403), r.status_code


@pytest.mark.django_db
class TestГдеЕщёВыбираютЧеловека:
    """Жалоба была не только про специалистов: «такая же дыра в остальных местах»."""

    @pytest.mark.parametrize(
        "model_admin, field",
        [
            (Specialist, "user"),
            (Notification, "user"),
            (Family, "owner"),
            (Product, "owner"),
        ],
    )
    def test_поле_человека_стало_списком(self, model_admin, field):
        site_admin = admin.site._registry[model_admin]

        assert field in site_admin.autocomplete_fields, "%s.%s всё ещё вводится вручную" % (model_admin, field)
        assert field not in (site_admin.raw_id_fields or ())

    def test_участник_семьи_во_вложенной_форме_тоже(self):
        """Семью собирают из людей — здесь выбор нужен не меньше."""
        from apps.family.admin import FamilyMemberInline

        assert "user" in FamilyMemberInline.autocomplete_fields
        assert FamilyMember is FamilyMemberInline.model
