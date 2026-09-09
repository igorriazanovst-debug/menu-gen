"""MG_CANONCASE2: разовая правка регистра в каталоге.

Названия Title Case («Сыр Чеддер») остались в каталоге с тех пор, когда
канонизация ещё не приводила регистр. Команда правит их задним числом, и вся её
сложность в одном: часть новых имён уже занята. У `Product.name` нет
unique-ограничения, поэтому слепое переименование не упало бы с ошибкой, а тихо
положило рядом вторую «Сыр пармезан» — то есть сделало бы хуже, чем было.

Проверяется поэтому не «переименовалось ли», а границы: что команда трогает,
что сливает, чего не трогает вовсе и что при слиянии не теряется.

Названия выдуманы — в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), и совпадение с ним ловилось бы как ошибка команды.
"""

import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from apps.family.models import Family
from apps.fridge.models import FridgeItem, Product, ProductAlias
from apps.menu.models import Menu, MenuItem
from apps.users.models import User


def run(*args):
    out = StringIO()
    call_command("mg_fix_product_case", *args, stdout=out)
    return out.getvalue()


def auto(name, **kw):
    return Product.objects.create(name=name, source=Product.Source.AUTO, **kw)


@pytest.fixture
def family(db):
    user = User.objects.create_user(email="hozyain@example.test", name="Хозяин", password="pwd12345!")
    return Family.objects.create(owner=user, name="Семья Проверочная")


class TestWhatGetsRenamed:
    def test_title_case_is_lowered(self, db):
        p = auto("Сыр Выдуманный Твёрдый")
        run("--apply")
        p.refresh_from_db()
        assert p.name == "Сыр выдуманный твёрдый"

    def test_brand_survives(self, db):
        # Ровно эти шесть названий испортила бы прежняя, сплошная версия правила.
        for name in [
            "Камамбер Vitaltest",
            "Паста Aroy-test карри",
            "Рис Arboriotest",
            "Соус выдуманный Zerotest",
            'Тесто для вареников "Тестовъ"',
            "Яйцо - 1 шт. С1",
        ]:
            auto(name)
        run("--apply")
        for name in ["Камамбер Vitaltest", "Рис Arboriotest", "Яйцо - 1 шт. С1"]:
            assert Product.objects.filter(name=name).exists(), name

    def test_family_product_is_not_touched(self, db, family):
        # Продукт семьи — её дело: имя ей писать, а не каталогу.
        p = auto("Своя Выдуманная Заготовка", owner_family=family)
        run("--apply")
        p.refresh_from_db()
        assert p.name == "Своя Выдуманная Заготовка"

    def test_other_sources_are_not_touched_by_default(self, db):
        p = Product.objects.create(name="Ручная Выдуманная Запись", source=Product.Source.MANUAL)
        run("--apply")
        p.refresh_from_db()
        assert p.name == "Ручная Выдуманная Запись"

    def test_source_all_reaches_them(self, db):
        p = Product.objects.create(name="Ручная Выдуманная Запись", source=Product.Source.MANUAL)
        run("--apply", "--source", "all")
        p.refresh_from_db()
        assert p.name == "Ручная выдуманная запись"


class TestDryRunIsTheDefault:
    def test_nothing_changes_without_apply(self, db):
        p = auto("Сыр Выдуманный Твёрдый")
        out = run()
        p.refresh_from_db()
        assert p.name == "Сыр Выдуманный Твёрдый"
        assert "DRY-RUN" in out

    def test_both_lists_are_printed_in_full(self, db):
        auto("Сыр Выдуманный Твёрдый")
        dup = auto("Сыр Выдуманный Мягкий")
        Product.objects.create(name="Сыр выдуманный мягкий", source=Product.Source.MANUAL)
        out = run()
        assert "Сыр выдуманный твёрдый" in out
        assert str(dup.id) in out


class TestCollisions:
    """Новое имя занято — переименовать нельзя, дублей быть не должно."""

    def test_not_renamed_without_merge(self, db):
        canon = Product.objects.create(name="Сыр выдуманный мягкий", source=Product.Source.MANUAL)
        dup = auto("Сыр Выдуманный Мягкий")
        run("--apply")
        dup.refresh_from_db()
        assert dup.name == "Сыр Выдуманный Мягкий"
        assert Product.objects.filter(name="Сыр выдуманный мягкий").count() == 1
        assert Product.objects.filter(id=canon.id).exists()

    def test_merge_moves_links_and_drops_the_duplicate(self, db, family):
        canon = Product.objects.create(name="Сыр выдуманный мягкий", source=Product.Source.MANUAL)
        dup = auto("Сыр Выдуманный Мягкий")
        item = FridgeItem.objects.create(family=family, name="сыр", product=dup)

        run("--apply", "--merge")

        assert not Product.objects.filter(id=dup.id).exists()
        item.refresh_from_db()
        assert item.product_id == canon.id
        # Синонима не заводится, и это правильно: имена различались только
        # регистром, а поиск по синонимам и так регистронезависим.
        assert not ProductAlias.objects.filter(product=canon).exists()
        assert Product.objects.filter(name="Сыр выдуманный мягкий").count() == 1

    def test_menu_position_survives_the_merge(self, db, family):
        """MG_MERGEALL: у MenuItem.product стоит CASCADE.

        Слияние удаляет дубль. Пока перепривязка шла по списку из трёх моделей,
        позиция меню с этим продуктом исчезала бы вместе с ним — молча, без
        ошибки, и заметить это можно было бы только по пустому дню в меню.
        """
        canon = Product.objects.create(name="Сыр выдуманный мягкий", source=Product.Source.MANUAL)
        dup = auto("Сыр Выдуманный Мягкий")
        menu = Menu.objects.create(
            family=family,
            creator_id=family.owner_id,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 7),
        )
        pos = MenuItem.objects.create(menu=menu, product=dup, meal_type="breakfast", day_offset=0, grams=40)

        run("--apply", "--merge")

        pos.refresh_from_db()
        assert pos.product_id == canon.id

    def test_ambiguous_target_is_skipped(self, db, family):
        """Под новым именем — продукт чужой семьи. Механически тут не разобрать."""
        Product.objects.create(name="Сыр выдуманный мягкий", source=Product.Source.MANUAL, owner_family=family)
        dup = auto("Сыр Выдуманный Мягкий")

        out = run("--apply", "--merge")

        dup.refresh_from_db()
        assert dup.name == "Сыр Выдуманный Мягкий"
        assert "Пропущено" in out
