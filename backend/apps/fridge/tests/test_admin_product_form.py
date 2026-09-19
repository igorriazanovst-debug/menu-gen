"""MG_ADMINFORM: форму товара должно быть видно, что заполнять.

Отчёт с прода: «в админке добавить решительно нельзя, куча неочевидных пунктов,
без подсказок, без выпадающих списков». Так и было: два десятка полей подряд,
рубрика — поле для ввода номера (raw_id), половина полей вообще про импорт
штрих-кодов, а не про ручное заведение. Кончилось тем, что два товара пришлось
заводить скриптом через shell.

Проверяется поведение формы, а не вёрстка: рубрика — выпадающий список и
обязательна (товар без рубрики уезжает в «Прочее»), старого текстового поля
категории в форме нет, разделы на месте.
"""

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.fridge.admin import ProductAdmin
from apps.fridge.models import Product, ProductCategory

# MG_UNITNORM: служебные поля раздела «Вес единицы». Их шлёт любой браузер,
# даже если человек в раздел не заглядывал, — без них Django отвергает всю
# форму целиком.
_EMPTY_INLINE = {
    "unit_weights-TOTAL_FORMS": "0",
    "unit_weights-INITIAL_FORMS": "0",
    "unit_weights-MIN_NUM_FORMS": "0",
    "unit_weights-MAX_NUM_FORMS": "1000",
}


@pytest.fixture
def staff_client(db, client):
    User = get_user_model()
    user = User.objects.create_superuser(email="admin@example.com", password="pass12345", name="Админ")
    client.force_login(user)
    return client


def _form():
    """Готовая форма из админки: часть полей она подменяет сама, часть — __init__."""
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    request = RequestFactory().get("/admin/fridge/product/add/")
    request.user = AnonymousUser()
    return ProductAdmin(Product, django_admin.site).get_form(request)()


@pytest.mark.django_db
class TestПоляФормы:
    def test_рубрика_выпадающим_списком(self):
        """Ввод номера рубрики руками — то, на что и жаловались."""
        from django.contrib.admin.widgets import ForeignKeyRawIdWidget
        from django.forms import Select

        field = _form().fields["category_fk"]
        # Админка оборачивает список в RelatedFieldWidgetWrapper (это кнопка «+»
        # рядом), поэтому смотрим внутрь обёртки.
        inner = getattr(field.widget, "widget", field.widget)

        assert isinstance(inner, Select)
        assert not isinstance(inner, ForeignKeyRawIdWidget)

    def test_рубрика_обязательна(self):
        """Товар без рубрики уезжает в «Прочее» — это мы уже разгребали."""
        assert _form().fields["category_fk"].required is True

    def test_неактивные_рубрики_не_предлагаются(self):
        ProductCategory.objects.filter(slug="other").update(is_active=True)
        dead = ProductCategory.objects.create(slug="плюмбусы", name_ru="Плюмбусы", is_active=False)

        field = _form().fields["category_fk"]

        assert dead not in field.queryset

    def test_старой_текстовой_категории_в_форме_нет(self):
        """Её заполняет импорт OFF; руками она только путает."""
        assert "category" not in _form().fields

    def test_у_имени_и_рубрики_есть_подсказки(self):
        fields = _form().fields

        assert fields["name"].help_text
        assert fields["category_fk"].help_text


@pytest.mark.django_db
class TestСтраницаДобавления:
    def test_страница_открывается_и_разложена_по_разделам(self, staff_client):
        page = staff_client.get(reverse("admin:fridge_product_add"))

        assert page.status_code == 200
        body = page.content.decode()
        assert "Главное" in body
        assert 'name="category_fk"' in body

    def test_товар_заводится_с_главного_раздела(self, staff_client):
        """MG_ADMINKBJU: свёрнутые разделы можно не открывать.

        КБЖУ хранится с default=dict, но в форме было обязательным: Django
        считает пустой словарь пустым значением. Товар не сохранялся, пока не
        откроешь свёрнутый раздел и не впишешь туда JSON, — а сообщение об
        ошибке пряталось там же.
        """
        cat = ProductCategory.objects.filter(slug="meat").first() or ProductCategory.objects.create(
            slug="meat", name_ru="Мясо и птица", is_active=True
        )

        staff_client.post(
            reverse("admin:fridge_product_add"),
            {
                "name": "Плюмбус копчёный",
                "category_fk": cat.id,
                "default_unit": "г",
                "source": Product.Source.MANUAL,
                # MG_UNITNORM: у страницы появился раздел «Вес единицы».
                # Браузер шлёт его служебные поля всегда, даже когда человек
                # туда не заглядывал; без них форма не проходит проверку, и
                # товар молча не сохраняется — ровно та беда, про которую этот
                # тест и написан.
                **_EMPTY_INLINE,
            },
        )

        p = Product.objects.filter(name="Плюмбус копчёный").first()
        assert p is not None
        assert p.category_fk_id == cat.id
        assert p.nutrition == {}

    def test_без_рубрики_не_сохраняется(self, staff_client):
        page = staff_client.post(
            reverse("admin:fridge_product_add"),
            {"name": "Плюмбус безрубричный", "source": Product.Source.MANUAL, **_EMPTY_INLINE},
        )

        assert page.status_code == 200  # форма вернулась с ошибкой, а не сохранилась
        assert not Product.objects.filter(name="Плюмбус безрубричный").exists()
