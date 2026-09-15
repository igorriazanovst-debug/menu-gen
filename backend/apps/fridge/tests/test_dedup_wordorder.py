"""MG_WORDORDER: «Соус соевый» и «Соевый соус» — один товар, а не два.

На проде таких пар 38. Часть с большим числом ссылок сразу: «Растительное
масло» (227 связей) рядом с «масло растительное», «Лук репчатый» (629) рядом с
«Репчатый лук», «Панировочные сухари» (23) рядом с «Сухари панировочные» (33).
В списке покупок пара расходится на две строки, и человек видит один и тот же
товар дважды.

Обычная нормализация их не ловит: она сравнивает строку целиком и слова не
переставляет.

Названия продуктов в тесте выдуманные. Посевная миграция заводит каталог в
каждую тестовую базу, и взятое оттуда название слилось бы с посевной записью —
проверка показывала бы не то, что проверяет.
"""

import pytest
from django.core.management import call_command

from apps.family.models import Family
from apps.fridge.management.commands.dedup_products import wordorder_key
from apps.fridge.models import Product
from apps.users.models import User
from apps.users.views import _bootstrap_user


class TestКлюч:
    def test_перестановка_слов_даёт_один_ключ(self):
        assert wordorder_key("Соевый соус") == wordorder_key("Соус соевый")
        assert wordorder_key("Лук репчатый") == wordorder_key("Репчатый лук")
        assert wordorder_key("Панировочные сухари") == wordorder_key("Сухари панировочные")
        assert wordorder_key("Орех грецкий") == wordorder_key("Грецкий орех")

    def test_регистр_и_ё_не_мешают(self):
        assert wordorder_key("масло растительное") == wordorder_key("Растительное масло")
        assert wordorder_key("Лук зелёный") == wordorder_key("Зеленый лук")

    def test_дефис_считается_пробелом(self):
        """«Лук-порей» и «Лук порей» на проде лежат обеими записями."""
        assert wordorder_key("Лук-порей") == wordorder_key("Лук порей")

    def test_однословные_правилу_не_подлежат(self):
        """Для одного слова правило совпадает с обычной нормализацией."""
        assert wordorder_key("Соль") is None
        assert wordorder_key("Молоко") is None

    def test_разные_товары_не_сходятся(self):
        assert wordorder_key("Масло сливочное") != wordorder_key("Масло растительное")
        assert wordorder_key("Перец чёрный") != wordorder_key("Перец красный")


@pytest.mark.django_db
class TestСлияние:
    def _pair(self):
        a = Product.objects.create(name="Плюмбус кварцевый", source=Product.Source.MANUAL)
        b = Product.objects.create(name="Кварцевый плюмбус", source=Product.Source.AUTO)
        return a, b

    def test_без_флага_пара_остаётся_как_была(self):
        a, b = self._pair()

        call_command("dedup_products")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2

    def test_с_флагом_но_без_apply_ничего_не_пишется(self):
        a, b = self._pair()

        call_command("dedup_products", "--wordorder")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2

    def test_с_флагом_и_apply_пара_сливается_в_одну(self):
        a, b = self._pair()

        call_command("dedup_products", "--wordorder", "--apply")

        left = list(Product.objects.filter(id__in=[a.id, b.id]))
        assert len(left) == 1
        # Канон — запись с меньшим id при прочих равных.
        assert left[0].id == a.id


@pytest.mark.django_db
class TestГраницыСлияния:
    """MG_DEDUPSCOPE: что дедупликация трогать не должна.

    На проде с --wordorder она предлагала «курица» → «Курица (филе)» и «Молодой
    горошек» → «Молодой горошек (консервы овощные стерилизованные: горошек
    зеленый)». Канон выбирается по наличию КБЖУ, а КБЖУ есть у упаковок из
    справочника штрих-кодов — и настоящие продукты уезжали на записи, скрытые
    из всех подборщиков.
    """

    def test_упаковка_из_справочника_каноном_не_становится(self, db):
        from apps.fridge.dedup import has_kbju  # noqa: F401  — для читателя: канон выбирается по КБЖУ

        pack = Product.objects.create(
            name="Плюмбус кварцевый (упаковка 500 г)",
            source=Product.Source.OFFBULK,
            barcode="4600000000009",
            calories_per_100g=100,
        )
        real = Product.objects.create(name="Кварцевый плюмбус", source=Product.Source.AUTO)
        twin = Product.objects.create(name="Плюмбус кварцевый", source=Product.Source.AUTO)

        call_command("dedup_products", "--wordorder", "--apply")

        pack.refresh_from_db()
        assert pack.name == "Плюмбус кварцевый (упаковка 500 г)"
        assert Product.objects.filter(id__in=[real.id, twin.id]).count() == 1

    def test_продукт_семьи_не_сливается_с_общим(self, db):
        owner = User.objects.create_user(email="dedup@example.com", password="pass12345", name="O")
        _bootstrap_user(owner)
        family = Family.objects.get(owner=owner)
        own = Product.objects.create(name="Шмурдяк ягодный", source=Product.Source.MANUAL, owner_family=family)
        common = Product.objects.create(name="Ягодный шмурдяк", source=Product.Source.AUTO)

        call_command("dedup_products", "--wordorder", "--apply")

        own.refresh_from_db()
        common.refresh_from_db()
        assert own.name == "Шмурдяк ягодный"
        assert common.name == "Ягодный шмурдяк"

    def test_каноном_становится_запись_с_обычным_написанием(self, db):
        """Имя канона уезжает во все списки покупок, поэтому оно важно."""
        shouty = Product.objects.create(name="Тунец В Собственном Соку", source=Product.Source.AUTO)
        plain = Product.objects.create(name="Тунец в собственном соку", source=Product.Source.AUTO)

        call_command("dedup_products", "--wordorder", "--apply")

        left = list(Product.objects.filter(id__in=[shouty.id, plain.id]))
        assert len(left) == 1
        assert left[0].name == "Тунец в собственном соку"
