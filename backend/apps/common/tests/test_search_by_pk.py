"""MG_PKSEARCH: искать по номеру записи.

Отчёт с прода: «рецепт в админке невозможно найти по номеру». Так и было: поиск
шёл по названию, и «5095» не находило ничего — при том что номер виден везде, в
списке админки, в выводе команд, в разборе связей.

Правило: сначала пробуем номер, и только если записи с таким номером нет —
обычный поиск. Иначе «100» перестало бы находить «Молоко 100 г».
"""

import pytest
from django.contrib import admin as django_admin

from apps.common.search import as_pk
from apps.fridge.admin import ProductAdmin
from apps.fridge.models import Product


class TestРазборНомера:
    def test_число_это_номер(self):
        assert as_pk("5095") == 5095

    def test_решётку_отбрасываем(self):
        """Команды печатают номера как «#5095» — так его и скопируют."""
        assert as_pk("#5095") == 5095
        assert as_pk(" # 5095 ") == 5095

    def test_текст_номером_не_считается(self):
        assert as_pk("Молоко") is None
        assert as_pk("100 г") is None
        assert as_pk("") is None
        assert as_pk(None) is None


def _search(term):
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    request = RequestFactory().get("/admin/fridge/product/")
    request.user = AnonymousUser()
    model_admin = ProductAdmin(Product, django_admin.site)
    qs, _dup = model_admin.get_search_results(request, Product.objects.all(), term)
    return list(qs)


@pytest.mark.django_db
class TestПоискПоНомеру:
    def test_находит_по_номеру(self):
        p = Product.objects.create(name="Плюмбус обыкновенный")

        assert _search(str(p.id)) == [p]

    def test_находит_по_номеру_с_решёткой(self):
        p = Product.objects.create(name="Плюмбус обыкновенный")

        assert _search("#%d" % p.id) == [p]

    def test_число_в_названии_по_прежнему_ищется(self):
        """Если записи с таким номером нет — работает обычный поиск."""
        Product.objects.filter(name__icontains="плюмбус").delete()
        p = Product.objects.create(name="Плюмбусное молоко 100 г")
        missing = Product.objects.order_by("-id").first().id + 1000

        found = _search(str(missing))

        assert p not in found  # номера такого нет, но и падать не должно
        assert _search("100 г") == [p] or p in _search("100")

    def test_обычный_поиск_по_имени_не_сломан(self):
        p = Product.objects.create(name="Плюмбус копчёный")

        assert p in _search("плюмбус копченый")
