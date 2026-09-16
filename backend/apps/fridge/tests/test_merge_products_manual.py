"""MG_MERGEMANUAL: слить названные записи руками.

Автоматика добирает не всё. «Лука» в родительном падеже живёт в каталоге одна,
канон у неё «лук», записи «Лук» нет — есть «Лук репчатый». Группы не выходит,
и в списке покупок остаётся лишняя строка «Лука — 60.00 г». Решение тут
человеческое, а команда только выполняет и показывает цену.

Названия выдуманы: посевная миграция заводит свой каталог в каждую тестовую базу.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.family.models import Family
from apps.fridge.models import Product
from apps.users.models import User


def _run(*args):
    out = StringIO()
    call_command("mg_merge_products", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.mark.django_db
class TestРучноеСлияние:
    def test_dry_run_ничего_не_пишет(self):
        canon = Product.objects.create(name="Плюмбус репчатый")
        dup = Product.objects.create(name="Плюмбуса")

        out = _run(str(canon.id), str(dup.id))

        assert Product.objects.filter(id=dup.id).exists()
        assert "DRY-RUN" in out

    def test_слияние_выполняется(self):
        canon = Product.objects.create(name="Плюмбус репчатый")
        dup = Product.objects.create(name="Плюмбуса")

        _run(str(canon.id), str(dup.id), "--apply")

        assert Product.objects.filter(id=canon.id).exists()
        assert not Product.objects.filter(id=dup.id).exists()

    def test_несколько_дублей_за_раз(self):
        canon = Product.objects.create(name="Плюмбус репчатый")
        a = Product.objects.create(name="Плюмбуса")
        b = Product.objects.create(name="Плюмбусов")

        _run(str(canon.id), str(a.id), str(b.id), "--apply")

        assert not Product.objects.filter(id__in=[a.id, b.id]).exists()

    def test_несуществующий_номер_это_ошибка(self):
        canon = Product.objects.create(name="Плюмбус репчатый")

        with pytest.raises(CommandError, match="нет в каталоге"):
            _run(str(canon.id), "99999999")

    def test_саму_в_себя_не_сливаем(self):
        canon = Product.objects.create(name="Плюмбус репчатый")

        with pytest.raises(CommandError, match="саму в себя"):
            _run(str(canon.id), str(canon.id))

    def test_продукт_семьи_не_трогаем(self):
        """Он виден только своей семье — слияние меняло бы чужие списки."""
        owner = User.objects.create_user(email="fam@example.com", password="pass12345", name="Owner")
        family = Family.objects.create(name="Семья", owner=owner)
        canon = Product.objects.create(name="Плюмбус репчатый")
        theirs = Product.objects.create(name="Мамин плюмбус", owner_family=family)

        with pytest.raises(CommandError, match="продукт семьи"):
            _run(str(canon.id), str(theirs.id))

    def test_скрытую_из_подборщиков_запись_не_трогаем(self):
        canon = Product.objects.create(name="Плюмбус репчатый")
        hidden = Product.objects.create(name="Плюмбус 400 г", source=Product.Source.RETAIL)

        with pytest.raises(CommandError, match="скрыт"):
            _run(str(canon.id), str(hidden.id))

    def test_переименование_канона(self):
        """MG_MERGERENAME: годного имени нет ни у одной записи группы.

        «Агара» и «Агар агара» — правильного «Агар-агар» в каталоге нет вовсе.
        Слияние без переименования оставило бы кривое имя во всех ссылках.
        """
        canon = Product.objects.create(name="Плюмбуса")
        dup = Product.objects.create(name="Плюмбус плюмбуса")

        _run(str(canon.id), str(dup.id), "--name", "Плюмбус-плюмбус", "--apply")

        canon.refresh_from_db()
        assert canon.name == "Плюмбус-плюмбус"
        assert not Product.objects.filter(id=dup.id).exists()

    def test_старое_имя_остаётся_синонимом(self):
        """По нему ищут связи рецептов и разбор состава — терять его нельзя."""
        from apps.fridge.models import ProductAlias

        canon = Product.objects.create(name="Плюмбуса")
        dup = Product.objects.create(name="Плюмбус плюмбуса")

        _run(str(canon.id), str(dup.id), "--name", "Плюмбус-плюмбус", "--apply")

        from apps.fridge.aliases import normalize_alias

        aliases = set(ProductAlias.objects.filter(product=canon).values_list("alias_norm", flat=True))
        assert normalize_alias("Плюмбуса") in aliases

    def test_имя_с_примечанием_не_принимается(self):
        canon = Product.objects.create(name="Плюмбуса")
        dup = Product.objects.create(name="Плюмбус плюмбуса")

        with pytest.raises(CommandError, match="не название продукта"):
            _run(str(canon.id), str(dup.id), "--name", "Плюмбус для обжарки", "--apply")

    def test_столкновение_с_существующей_записью_это_ошибка(self):
        """Иначе в каталоге завелось бы второе имя того же товара — новый дубль."""
        canon = Product.objects.create(name="Плюмбуса")
        dup = Product.objects.create(name="Плюмбус плюмбуса")
        Product.objects.create(name="Плюмбус-плюмбус")

        with pytest.raises(CommandError, match="уже есть"):
            _run(str(canon.id), str(dup.id), "--name", "Плюмбус-плюмбус", "--apply")

    def test_цена_ошибки_видна_до_записи(self):
        """Сколько ссылок переедет — в dry-run, а не в отчёте после."""
        from apps.recipes.models import Recipe, RecipeProduct

        canon = Product.objects.create(name="Плюмбус репчатый")
        dup = Product.objects.create(name="Плюмбуса")
        recipe = Recipe.objects.create(title="Блюдо с плюмбусом", ingredients=[])
        RecipeProduct.objects.create(recipe=recipe, name_canonical="Плюмбуса", name_raw="плюмбуса", product=dup)

        out = _run(str(canon.id), str(dup.id))

        assert "связей рецептов к переносу: 1" in out
