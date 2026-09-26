"""MG_PACKSIZE: заполнение весов разбором фасовки из каталога.

Фасовка розничных товаров уже лежит в `Product.default_unit` строкой — импорт
справочников сетей кладёт её туда. Команда её читает и заводит вес упаковки:
это не догадка, а чтение того, что есть.

Проверяется в первую очередь то, чего команда делать НЕ должна: писать без
`--apply`, трогать уже заданные веса и заводить «штуку». Последнее — главное.
Одна упаковка это всегда пачка целиком, а одна штука бывает и пачкой, и
отдельной оливкой из банки; записав пачку как штуку, мы получили бы «25 шт
оливок = 7,5 кг».

Названия выдуманы: посевная миграция заводит каталог в каждую тестовую базу.
Там же есть товары с разбираемой фасовкой — «Вода газированная» с «1.5л»,
например. Поэтому проверять надо свои записи, а не общее число строк: счётчики
в выводе команды считают и посевные тоже.
"""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.fridge.models import Product, ProductUnitWeight


def run(*args):
    out = StringIO()
    call_command("mg_unit_weights", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def retail(db):
    """Товар из справочника сети: в default_unit лежит фасовка строкой."""
    return Product.objects.create(name="Плюмбус творожный", default_unit="250 г")


@pytest.mark.django_db
class TestРазборКаталога:
    def test_dry_run_ничего_не_пишет(self, retail):
        out = run("--from-catalog")

        assert "dry-run" in out
        assert f"#{retail.id}" in out  # в списке к записи он есть
        assert not ProductUnitWeight.objects.filter(product=retail).exists()

    def test_с_apply_заводит_вес_упаковки(self, retail):
        run("--from-catalog", "--apply")

        row = ProductUnitWeight.objects.get(product=retail)
        assert row.unit == "упаковка"
        assert row.grams == Decimal("250.00")
        assert row.source == ProductUnitWeight.Source.SEED

    def test_штуку_не_заводит(self, retail):
        """Главное правило: пачка не равна штуке.

        «1 упаковка» — всегда пачка целиком. «1 шт» бывает и пачкой, и
        отдельной оливкой из банки, и записать сюда вес пачки значит однажды
        списать из холодильника в десятки раз больше, чем ушло.
        """
        run("--from-catalog", "--apply")

        assert not ProductUnitWeight.objects.filter(product=retail, unit="шт").exists()

    def test_обычную_единицу_пропускает(self, db):
        """У большинства товаров в default_unit единица, а не фасовка."""
        product = Product.objects.create(name="Плюмбус обычный", default_unit="шт")

        run("--from-catalog", "--apply")

        assert not ProductUnitWeight.objects.filter(product=product).exists()

    def test_заданный_вес_не_перезаписывает(self, retail):
        """Человек и модель важнее строки из справочника."""
        ProductUnitWeight.objects.create(
            product=retail, unit="упаковка", grams=Decimal("400"), source=ProductUnitWeight.Source.MANUAL
        )

        out = run("--from-catalog", "--apply")

        row = ProductUnitWeight.objects.get(product=retail, unit="упаковка")
        assert row.grams == Decimal("400.00")
        assert row.source == ProductUnitWeight.Source.MANUAL
        assert "уже задан, не трогаем: 1" in out

    def test_повторный_запуск_не_плодит_строк(self, retail):
        run("--from-catalog", "--apply")
        run("--from-catalog", "--apply")

        assert ProductUnitWeight.objects.filter(product=retail).count() == 1

    def test_множитель_в_фасовке(self, db):
        product = Product.objects.create(name="Плюмбус порционный", default_unit="4.5 г x 4 шт")

        run("--from-catalog", "--apply")

        assert ProductUnitWeight.objects.get(product=product).grams == Decimal("18.00")

    def test_нелепую_фасовку_не_берёт(self, db):
        """50 кг в упаковке значит, что разобрали не ту часть строки."""
        product = Product.objects.create(name="Плюмбус исполинский", default_unit="50 кг")

        run("--from-catalog", "--apply")

        assert not ProductUnitWeight.objects.filter(product=product).exists()

    def test_limit_ограничивает_запись(self, db):
        """Записей ровно столько, сколько разрешено, чьи бы они ни были.

        Посевные товары с разбираемой фасовкой идут первыми по номеру и могут
        занять места — проверяется именно потолок, а не какие товары попали.
        """
        before = ProductUnitWeight.objects.count()
        for i in range(5):
            Product.objects.create(name="Плюмбус партия %d" % i, default_unit="200 г")

        run("--from-catalog", "--apply", "--limit", "2")

        assert ProductUnitWeight.objects.count() == before + 2

    def test_записанное_сразу_работает_в_переводе(self, retail):
        """Смысл всей операции: после неё упаковка сходится с граммами рецепта."""
        from apps.fridge.units import to_grams

        run("--from-catalog", "--apply")

        assert to_grams(Decimal("2"), "упаковка", retail.id) == Decimal("500.00")


@pytest.mark.django_db
class TestРасхождениеСНазванием:
    """Фасовка иногда описывает не упаковку, а то, из чего она состоит.

    Поймано на dry-run прода: у чая в поле фасовки «2 г» — это один пакетик, а
    множитель «x 100шт» остался в названии. Записав это, мы объявили бы пачку
    чая двумя граммами и получали нехватку на каждом рецепте — ошибка в сто раз
    и совершенно незаметная.
    """

    def test_чай_с_множителем_в_названии_пропускается(self, db):
        product = Product.objects.create(
            name="Чай Ahmad Tea Earl Grey черный с бергамотом (2г x 100шт), 200г",
            default_unit="2г",
        )

        out = run("--from-catalog", "--apply")

        assert not ProductUnitWeight.objects.filter(product=product).exists()
        assert "спорит с названием" in out

    def test_согласное_название_не_мешает(self, db):
        """Обычный случай: и в названии, и в фасовке одно и то же число."""
        product = Product.objects.create(name="Соус Плюмбус острый, 350мл", default_unit="350мл")

        run("--from-catalog", "--apply")

        assert ProductUnitWeight.objects.get(product=product).grams == Decimal("350.00")

    def test_название_без_размера_не_мешает(self, db):
        product = Product.objects.create(name="Вода плюмбусная негазированная", default_unit="1.5л")

        run("--from-catalog", "--apply")

        assert ProductUnitWeight.objects.get(product=product).grams == Decimal("1500.00")

    def test_коробка_из_стаканов_тоже_пропускается(self, db):
        """«40 г x 24 шт» — 960 г в коробке или 40 г в стакане?

        Из строки это не следует, и брать число из названия было бы такой же
        догадкой, как брать из фасовки. Пропускаем.
        """
        product = Product.objects.create(name="Пюре Плюмбус со вкусом курицы, 40г x 24 шт", default_unit="40г")

        run("--from-catalog", "--apply")

        assert not ProductUnitWeight.objects.filter(product=product).exists()
