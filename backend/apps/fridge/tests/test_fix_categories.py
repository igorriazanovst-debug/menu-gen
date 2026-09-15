"""MG_CATFIX: половина каталога лежит в «Прочем» — 598 записей из 1204 на dev.

В списке покупок это и видно: «Кальмар», «Гребешки», «Бекон сырокопчёный»,
«Крахмал», «Кунжут» стоят одной кучей. Это не мусор, а продукты без рубрики.

Модель здесь подменена: проверяется не качество её ответов, а границы команды —
что она разбирает, что пишет и когда отказывается писать.

Названия продуктов выдуманы: посевная миграция заводит каталог в каждую тестовую
базу, и совпадение с ним ловилось бы как ошибка команды.
"""

import json
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

from apps.family.models import Family
from apps.fridge.models import Product, ProductCategory
from apps.users.models import User
from apps.users.views import _bootstrap_user


@pytest.fixture
def cats(db):
    other, _ = ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее", "is_active": True})
    fish, _ = ProductCategory.objects.get_or_create(
        slug="fish", defaults={"name_ru": "Рыба и морепродукты", "is_active": True}
    )
    return other, fish


def answer(mapping):
    """Ответ модели: имя -> slug. Порядок в пачке не важен, сверяемся по имени."""

    def _complete(client, prompt, system, **kw):
        items = json.loads(prompt)
        return json.dumps([{"i": it["i"], "slug": mapping.get(it["name"], "other")} for it in items])

    return _complete


def run(*args, complete=None, boom=False):
    out, err = StringIO(), StringIO()
    if boom:

        def _complete(*a, **kw):
            raise RuntimeError("Read timed out. (read timeout=30.0)")

        complete = _complete
    with (
        mock.patch("apps.fridge.management.commands.mg_fix_categories.complete_with_retry", complete),
        mock.patch("apps.common.ai_provider.get_batch_ai_client"),
        mock.patch("apps.common.ai_provider.check_ai_available"),
    ):
        call_command("mg_fix_categories", *args, stdout=out, stderr=err)
    return out.getvalue() + err.getvalue()


@pytest.mark.django_db
class TestЧтоРазбирается:
    def test_запись_из_прочего_получает_рубрику(self, cats):
        other, _fish = cats
        p = Product.objects.create(name="Плюмбус морской", source=Product.Source.AUTO, category_fk=other)

        run("--apply", complete=answer({"Плюмбус морской": "fish"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "fish"

    def test_запись_без_рубрики_тоже_берётся(self, cats):
        p = Product.objects.create(name="Плюмбус донный", source=Product.Source.AUTO, category_fk=None)

        run("--apply", complete=answer({"Плюмбус донный": "fish"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "fish"

    def test_запись_с_рубрикой_не_трогается(self, cats):
        _other, fish = cats
        p = Product.objects.create(name="Плюмбус речной", source=Product.Source.AUTO, category_fk=fish)

        out = run("--apply", complete=answer({"Плюмбус речной": "vegetables"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "fish"
        assert "Записей без рубрики или в «Прочем»: 0" in out

    def test_справочник_штрихкодов_не_разбирается(self, cats):
        other, _fish = cats
        pack = Product.objects.create(
            name="Плюмбус морской (упаковка)",
            source=Product.Source.OFFBULK,
            barcode="4600000000011",
            category_fk=other,
        )

        run("--apply", complete=answer({"Плюмбус морской (упаковка)": "fish"}))

        pack.refresh_from_db()
        assert pack.category_fk.slug == "other"

    def test_продукт_семьи_не_разбирается(self, cats):
        other, _fish = cats
        owner = User.objects.create_user(email="cat@example.com", password="pass12345", name="O")
        _bootstrap_user(owner)
        family = Family.objects.get(owner=owner)
        p = Product.objects.create(
            name="Плюмбус семейный", source=Product.Source.MANUAL, category_fk=other, owner_family=family
        )

        run("--apply", complete=answer({"Плюмбус семейный": "fish"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "other"


@pytest.mark.django_db
class TestЧтоНеПишется:
    def test_без_apply_ничего_не_меняется(self, cats):
        other, _fish = cats
        p = Product.objects.create(name="Плюмбус глубинный", source=Product.Source.AUTO, category_fk=other)

        out = run(complete=answer({"Плюмбус глубинный": "fish"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "other"
        assert "DRY-RUN" in out

    def test_рубрика_вне_списка_игнорируется(self, cats):
        """Ответ модели — не решение: несуществующий slug пропускаем."""
        other, _fish = cats
        p = Product.objects.create(name="Плюмбус странный", source=Product.Source.AUTO, category_fk=other)

        run("--apply", complete=answer({"Плюмбус странный": "звездолёты"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "other"

    def test_other_в_ответе_не_считается_находкой(self, cats):
        other, _fish = cats
        p = Product.objects.create(name="Плюмбус безродный", source=Product.Source.AUTO, category_fk=other)

        out = run("--apply", complete=answer({}))

        p.refresh_from_db()
        assert p.category_fk.slug == "other"
        assert "Остаётся в «Прочем» — 1" in out

    def test_при_потерянной_пачке_запись_отменяется(self, cats):
        """Неполный разбор — не итог. Иначе «разложено 0» читалось бы как «нечего»."""
        other, _fish = cats
        p = Product.objects.create(name="Плюмбус утраченный", source=Product.Source.AUTO, category_fk=other)

        out = run("--apply", boom=True)

        p.refresh_from_db()
        assert p.category_fk.slug == "other"
        assert "Пачек не разобрано: 1 из 1" in out
        assert "Запись отменена" in out


@pytest.mark.django_db
class TestРубрикаОрехов:
    """MG_NUTSCAT: орехи не сладости.

    На пробной сотне модель отправила в «Сладости» девять записей подряд —
    «Орехи», «Миндаль», «Арахис», «Фисташки», «Фундук», «Кедровые орешки».
    Ошибкой модели это не было: подходящей рубрики в списке не существовало, а
    в каталоге «Орех грецкий» лежал в «Специях и приправах» — единого правила
    не было вовсе.
    """

    def test_рубрика_заведена_миграцией(self, db):
        cat = ProductCategory.objects.filter(slug="nuts").first()
        assert cat is not None
        assert cat.name_ru == "Орехи и сухофрукты"
        assert cat.is_active

    def test_рубрика_предлагается_модели(self, db):
        """Строка со списком рубрик собирается из активных — значит nuts в ней."""
        from apps.recipes.recipe_products import _allowed_categories

        assert "nuts" in {slug for slug, _ru, _cid in _allowed_categories()}

    def test_орех_раскладывается_в_свою_рубрику(self, cats):
        other, _fish = cats
        p = Product.objects.create(name="Плюмбусовый орех", source=Product.Source.AUTO, category_fk=other)

        run("--apply", complete=answer({"Плюмбусовый орех": "nuts"}))

        p.refresh_from_db()
        assert p.category_fk.slug == "nuts"

    def test_миграция_чужие_записи_не_перекладывает(self, db):
        """Раскладывать существующее — работа команды с dry-run, не миграции."""
        sweets = ProductCategory.objects.filter(slug="sweets").first()
        assert sweets is not None
        p = Product.objects.create(name="Плюмбусовый миндаль", source=Product.Source.AUTO, category_fk=sweets)

        p.refresh_from_db()
        assert p.category_fk.slug == "sweets"
