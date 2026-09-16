"""MG_MERGEKEEP: слияние не должно делать запись беднее.

Из полей самого продукта merge_product_into переносило одно — КБЖУ. Остальное
уходило вместе с удалённым дублём: рубрика, признак курируемой записи,
картинка, единица, срок хранения, штрих-код.

Пока выжившим всегда была самая «богатая» запись, это почти не проявлялось.
После MG_DEDUPSURVIVOR выживший выбирается по имени, и в плане на dev честно
встали «Моцарелла» (#68) -> «Сыр моцарелла» (#601) и «Кальмары» (#86) ->
«Кальмар» (#1975): имя у выжившего правильное, а рубрики и КБЖУ у него может и
не быть. Без переноса полей такое слияние стёрло бы ровно те рубрики, которые
мы только что разложили отдельным прогоном на 591 запись.

Названия продуктов выдуманы: посевная миграция заводит свой каталог в каждую
тестовую базу, и «Помидоры» здесь дали бы чужую запись.
"""

import pytest

from apps.fridge.dedup import merge_product_into
from apps.fridge.models import Product, ProductCategory


def _cat(slug, name):
    cat, _ = ProductCategory.objects.get_or_create(slug=slug, defaults={"name_ru": name, "is_active": True})
    return cat


@pytest.mark.django_db
class TestРубрика:
    def test_рубрика_дубля_переезжает_в_канон_без_рубрики(self):
        fish = _cat("fish", "Рыба и морепродукты")
        canon = Product.objects.create(name="Плюмбус морской")
        dup = Product.objects.create(name="Плюмбусы морские", category_fk=fish)

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.category_fk_id == fish.id

    def test_прочее_у_канона_рубрикой_не_считается(self):
        other = _cat("other", "Прочее")
        fish = _cat("fish", "Рыба и морепродукты")
        canon = Product.objects.create(name="Плюмбус донный", category_fk=other)
        dup = Product.objects.create(name="Плюмбусы донные", category_fk=fish)

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.category_fk_id == fish.id

    def test_своя_рубрика_канона_не_перетирается(self):
        fish = _cat("fish", "Рыба и морепродукты")
        veg = _cat("vegetables", "Овощи")
        canon = Product.objects.create(name="Плюмбус речной", category_fk=fish)
        dup = Product.objects.create(name="Плюмбусы речные", category_fk=veg)

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.category_fk_id == fish.id


@pytest.mark.django_db
class TestПроисхождениеЗаписи:
    def test_курируемая_запись_не_разжалуется(self):
        """is_seed защищает от mg_prune_auto_products — потерять его нельзя."""
        canon = Product.objects.create(name="Сыр плюмбус", source=Product.Source.AUTO)
        dup = Product.objects.create(name="Плюмбус", is_seed=True, source=Product.Source.MANUAL)

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.is_seed is True
        assert canon.source == Product.Source.MANUAL

    def test_ручную_запись_авто_дубль_не_переписывает(self):
        canon = Product.objects.create(name="Сыр плюмбус", source=Product.Source.MANUAL)
        dup = Product.objects.create(name="Плюмбус", source=Product.Source.AUTO)

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.source == Product.Source.MANUAL


@pytest.mark.django_db
class TestОстальныеПоля:
    def test_картинка_единица_и_срок_хранения_переезжают(self):
        canon = Product.objects.create(name="Плюмбус свежий")
        dup = Product.objects.create(
            name="Плюмбусы свежие",
            image_url="https://example.com/plumbus.jpg",
            default_unit="шт",
            shelf_life_days=7,
        )

        stats = merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.image_url == "https://example.com/plumbus.jpg"
        assert canon.default_unit == "шт"
        assert canon.shelf_life_days == 7
        assert stats["fields"] == 3

    def test_заполненное_у_канона_остаётся_как_было(self):
        canon = Product.objects.create(name="Плюмбус сушёный", default_unit="кг")
        dup = Product.objects.create(name="Плюмбусы сушёные", default_unit="шт")

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.default_unit == "кг"

    def test_штрихкод_переезжает_и_не_ломает_ограничение(self):
        """Код уникален на всю таблицу: присвоить его можно только после удаления дубля."""
        canon = Product.objects.create(name="Плюмбус в упаковке")
        dup = Product.objects.create(name="Плюмбусы в упаковке", barcode="4600000000017")

        merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.barcode == "4600000000017"

    def test_кбжу_как_и_прежде(self):
        canon = Product.objects.create(name="Плюмбус питательный")
        dup = Product.objects.create(name="Плюмбусы питательные", nutrition={"proteins": 3}, calories_per_100g=120)

        stats = merge_product_into(dup, canon)

        canon.refresh_from_db()
        assert canon.nutrition == {"proteins": 3}
        assert stats["kbju"] == 1
