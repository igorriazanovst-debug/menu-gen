"""MG_ADMINRU: админка по-русски независимо от браузера.

`LocaleMiddleware` слушает `Accept-Language`. У редактора с английским
браузером админка открывалась по-английски целиком — при полном русском
каталоге и `LANGUAGE_CODE = "ru-ru"`. Проверяем, что заголовок больше не
решает за админку, и что API при этом свободу выбора сохранил.
"""

import pytest
from django.utils import translation

from apps.users.models import User


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="ru-admin@example.com", password="pass12345", name="Админ", is_staff=True, is_superuser=True
    )


@pytest.mark.django_db
class TestAdminAlwaysRussian:
    def test_английский_браузер_получает_русскую_админку(self, client, staff):
        client.force_login(staff)

        r = client.get("/admin/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

        assert r.status_code == 200
        assert r["Content-Language"] == "ru"
        # «Администрирование сайта» — строка из собственного каталога Django.
        assert "Администрирование" in r.content.decode()

    def test_русский_браузер_ничего_не_ломает(self, client, staff):
        client.force_login(staff)

        r = client.get("/admin/", HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9")

        assert r.status_code == 200
        assert r["Content-Language"] == "ru"

    def test_язык_не_протекает_в_следующий_запрос(self, client, staff):
        """Язык живёт в потоке, а поток переиспользуется под следующий запрос.

        Не вернуть прежний язык — значит покрасить в русский и то, что попадёт
        на этот поток следом.
        """
        client.force_login(staff)

        with translation.override("en"):
            client.get("/admin/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

            assert translation.get_language() == "en"

    def test_не_админские_пути_не_трогаем(self):
        """У API язык выбирает клиент — админское правило туда не лезет."""
        from apps.common.admin_locale import AdminRussianLocaleMiddleware

        seen = {}

        def view(request):
            from django.http import HttpResponse

            seen["lang"] = translation.get_language()
            return HttpResponse("ok")

        mw = AdminRussianLocaleMiddleware(view)

        class _Req:
            path = "/api/v1/recipes/"

        with translation.override("en"):
            response = mw(_Req())

        assert seen["lang"] == "en", "язык запроса подменён на не-админском пути"
        assert response.get("Content-Language") is None
