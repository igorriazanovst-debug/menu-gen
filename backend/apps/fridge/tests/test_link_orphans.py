"""MG_LINKORPHAN: имя связи, не находящее товар, — строка в «Прочем».

Список покупок строится из связей рецепт→продукт. Если по имени связи товар не
находится, позиция остаётся без товара и без рубрики. На проде это дало
«Сушеных трав», «Помидор черри», «Листика шалфея» в «Прочем» — 266 связей из
15465, 117 разных имён.

Почти всё это падежи и формы числа от того, что в каталоге уже есть. Правило
сводит их сравнением начал слов, а на неоднозначности отказывается: угадывать,
какое из двух «масел» имелось в виду, команда не должна.

Названия выдуманы: посевная миграция заводит свой каталог в каждую тестовую базу.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.fridge.aliases import normalize_alias
from apps.fridge.management.commands.mg_link_orphans import stem_key
from apps.fridge.models import Product, ProductAlias
from apps.recipes.models import Recipe, RecipeProduct


def _run(*args):
    out = StringIO()
    call_command("mg_link_orphans", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def _link(name):
    recipe = Recipe.objects.create(title="Блюдо " + name, ingredients=[])
    RecipeProduct.objects.create(recipe=recipe, name_canonical=name, name_raw=name.lower())


def _has_alias(name):
    """Свой синоним, а не «хоть один»: посевная миграция заводит их в каждую базу."""
    return ProductAlias.objects.filter(alias_norm=normalize_alias(name)).exists()


class TestКлючОснов:
    def test_падеж_и_число_ключ_не_меняют(self):
        assert stem_key("Сушеных трав") == stem_key("Сушёные травы")
        assert stem_key("Салата") == stem_key("Салат")
        assert stem_key("Рукколы") == stem_key("Руккола")

    def test_порядок_слов_ключ_не_меняет(self):
        assert stem_key("Молотой паприки") == stem_key("Паприка молотая")

    def test_разные_продукты_не_сливаются(self):
        assert stem_key("Сок лимона") != stem_key("Сок лайма")
        assert stem_key("Творог") != stem_key("Творожок сладкий")

    def test_пустое_имя_ключа_не_даёт(self):
        assert stem_key("") is None
        assert stem_key("   ") is None


@pytest.mark.django_db
class TestРазборСирот:
    def test_падежная_форма_получает_синоним(self):
        product = Product.objects.create(name="Плюмбусы сушёные")
        _link("Плюмбусов сушёных")

        out = _run("--apply")

        assert ProductAlias.objects.filter(product=product, alias_norm=normalize_alias("Плюмбусов сушёных")).exists()
        assert "Синонимов записано: 1" in out

    def test_dry_run_ничего_не_пишет(self):
        Product.objects.create(name="Плюмбусы сушёные")
        _link("Плюмбусов сушёных")

        out = _run()

        assert not _has_alias("Плюмбусов сушёных")
        assert "DRY-RUN" in out

    def test_на_двух_кандидатах_отказываемся(self):
        """Угадывать, какой из двух имелся в виду, команда не должна."""
        Product.objects.create(name="Плюмбусное масло")
        Product.objects.create(name="Плюмбусные масла")
        _link("Плюмбусного масла")

        _run("--apply")

        assert not _has_alias("Плюмбусного масла")

    def test_когда_товара_нет_вовсе(self):
        _link("Завроплюмбус копчёный")

        out = _run("--apply")

        assert not _has_alias("Завроплюмбус копчёный")
        assert "нет подходящего товара" in out

    def test_связь_с_найденным_товаром_в_сироты_не_попадает(self):
        product = Product.objects.create(name="Плюмбус обычный")
        RecipeProduct.objects.create(
            recipe=Recipe.objects.create(title="Блюдо", ingredients=[]),
            name_canonical="Плюмбус обычный",
            name_raw="плюмбус",
            product=product,
        )

        out = _run()

        assert "не наводятся на товар: 0" in out

    def test_скрытые_из_подборщиков_кандидатами_не_считаются(self):
        """Синоним на упаковку из справочника штрих-кодов увёл бы ингредиент на SKU."""
        Product.objects.create(name="Плюмбусы сушёные 400 г", source=Product.Source.RETAIL)
        _link("Плюмбусы сушёные 400 г")

        _run("--apply")

        assert not _has_alias("Плюмбусы сушёные 400 г")
