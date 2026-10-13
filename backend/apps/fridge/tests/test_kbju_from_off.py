"""MG_OFFKJ: КБЖУ из OpenFoodFacts — килоджоули и дозаполнение каталога.

Жалоба с живого приложения: «очень много продуктов без КБЖУ, например в
openfood facts». Причина оказалась не в том, что данных нет, а в том, что мы
их не брали: разбор ответа искал только килокалории, а у европейского товара
этикетка обязана нести килоджоули и не обязана — килокалории.

Названия в тестах выдуманные: посевная миграция заводит каталог продуктов в
каждую тестовую базу, и «Творог» там уже есть.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.family.models import Family
from apps.fridge.models import Product
from apps.fridge.services import _off_kcal
from apps.users.models import User


class TestКалорийностьИзOFF:
    def test_килокалории_берутся_как_есть(self):
        assert _off_kcal({"energy-kcal_100g": 250}) == 250

    def test_килоджоули_переводятся(self):
        # 1046 кДж — это 250 ккал: ровно то, что написано на пачке печенья,
        # у которой в OFF нет поля energy-kcal.
        assert _off_kcal({"energy_100g": 1046}) == 250.0

    def test_килокалории_важнее_килоджоулей(self):
        # Когда есть оба, пересчитывать нечего — берём готовое.
        assert _off_kcal({"energy-kcal_100g": 249, "energy_100g": 1046}) == 249

    def test_ноль_это_ответ_а_не_пропуск(self):
        # У воды ровно столько. Прежняя цепочка через `or` ноль теряла и
        # возвращала «неизвестно» — то есть враньё вместо факта.
        assert _off_kcal({"energy-kcal_100g": 0}) == 0

    def test_единица_килокалории_не_делится_ещё_раз(self):
        # Безымянное energy_100g обычно в кДж, но не всегда. Поделить
        # килокалории на 4,184 значит занизить их вчетверо и не заметить.
        assert _off_kcal({"energy_100g": 250, "energy_unit": "kcal"}) is None

    def test_поле_с_kj_в_имени_однозначно(self):
        assert _off_kcal({"energy-kj_100g": 418.4}) == 100.0

    def test_нелепое_число_лучше_пустого(self):
        # 99999 кДж — это 23 тысячи ккал на 100 г. Молчаливая подстановка
        # мусора хуже пустого поля: пустое видно, а неверное расходится по
        # дневнику и меню.
        assert _off_kcal({"energy_100g": 99999}) is None

    def test_мусор_отсеивается_и_в_готовых_килокалориях(self):
        # MG_OFFJUNK. Проверка стояла только на пересчёте из килоджоулей, а
        # готовые килокалории шли в базу как есть. На проде среди
        # восемнадцати тысяч записей нашлась одна с калорийностью больше ста
        # тысяч: поле numeric(7,2) её не приняло, и суточный прогон упал на
        # одиннадцати тысячах.
        assert _off_kcal({"energy-kcal_100g": 123456}) is None
        assert _off_kcal({"energy-kcal_100g": -5}) is None
        # А правдоподобное по-прежнему проходит.
        assert _off_kcal({"energy-kcal_100g": 900}) == 900
        assert _off_kcal({"energy-kcal_100g": 901}) is None

    def test_мусорное_макро_тоже_не_берём(self):
        from apps.fridge.services import _normalize_off_product

        fields = _normalize_off_product(
            {
                "product_name": "Плюмбус невозможный",
                "nutriments": {"proteins_100g": 1200, "fat_100g": 5, "carbohydrates_100g": -3},
            }
        )

        # Белка «1200 г на 100 г» не бывает. В JSON переполнения не случится,
        # но такое число разойдётся по дневнику и меню как факт.
        assert fields["nutrition"] == {"fats": 5.0}

    def test_нет_ничего_нет_и_ответа(self):
        assert _off_kcal({}) is None
        assert _off_kcal({"energy-kcal_100g": "—"}) is None


def _catalog(name, barcode, **kw):
    return Product.objects.create(name=name, barcode=barcode, source=Product.Source.OFF, **kw)


def _run(*args):
    out = StringIO()
    call_command("refill_kbju_from_off", *args, stdout=out)
    return out.getvalue()


def _off(kcal=None, proteins=None):
    """Ответ OFF как его отдаёт fetch_off_result: карточка плюс исход."""
    nutriments = {}
    if kcal is not None:
        nutriments["energy-kcal_100g"] = kcal
    if proteins is not None:
        nutriments["proteins_100g"] = proteins
    return {"product_name": "Плюмбус в глазури", "nutriments": nutriments}, "ok"


@pytest.mark.django_db
class TestДозаполнениеИзOFF:
    def test_пустому_продукту_проставляются_калории(self):
        p = _catalog("Плюмбус в глазури", "4600000000011")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250, proteins=7),
        ):
            _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g == 250
        assert p.nutrition["proteins"] == 7

    def test_существующее_значение_не_перезаписывается(self):
        # Разбираться, кто прав, — отдельная работа. Молча менять число под
        # человеком нельзя.
        p = _catalog("Плюмбус копчёный", "4600000000028", calories_per_100g=300)

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250, proteins=7),
        ):
            _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g == 300
        assert p.nutrition["proteins"] == 7  # а вот макро было пусто — его взяли

    def test_без_apply_ничего_не_пишется(self):
        p = _catalog("Плюмбус сушёный", "4600000000035")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ):
            out = _run("--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert "Ничего не записано" in out

    def test_личные_продукты_людей_не_трогаем(self):
        user = User.objects.create_user(email="own@example.com", password="x", name="O")
        family = Family.objects.create(name="Семья", owner=user)
        p = Product.objects.create(
            name="Плюмбус домашний", barcode="4600000000042", source=Product.Source.OFF, owner_family=family
        )

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ) as fetch:
            _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert fetch.call_count == 0

    def test_скрытые_источники_только_по_флагу(self):
        p = Product.objects.create(name="Плюмбус магазинный", barcode="4600000000059", source=Product.Source.OFFBULK)

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ):
            _run("--apply", "--sleep", "0")
            p.refresh_from_db()
            assert p.calories_per_100g is None

            _run("--apply", "--sleep", "0", "--include-hidden")
            p.refresh_from_db()
            assert p.calories_per_100g == 250

    def test_одна_кривая_запись_не_валит_прогон(self):
        # MG_OFFJUNK. Так и вышло на проде: суточный прогон упал на
        # одиннадцати тысячах из восемнадцати. Записанное до того уцелело, но
        # полсуток работы — нет. Проверка значений стоит выше по течению;
        # здесь — последний рубеж, потому что данные у OFF чужие и меняются.
        from django.db import DataError

        bad = _catalog("Плюмбус негодный", "4600000000134")
        good = _catalog("Плюмбус годный", "4600000000141")

        real_save = Product.save

        def save(self, *a, **kw):
            if self.pk == bad.pk:
                raise DataError("numeric field overflow")
            return real_save(self, *a, **kw)

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ):
            with patch.object(Product, "save", save):
                out = _run("--apply", "--sleep", "0")

        good.refresh_from_db()
        assert good.calories_per_100g == 250, "годная запись должна была сохраниться"
        assert "база не приняла" in out

    def test_отбор_по_источнику(self):
        # Нужно для замера. Выборка идёт по возрастанию id, и первые сотни
        # оказались сплошь retail — каталог торговой сети, которого в OFF нет
        # по определению. Отдача по нему (6%) ничего не говорит про off_bulk,
        # а именно его шестнадцать тысяч.
        Product.objects.create(name="Плюмбус сетевой", barcode="4600000000110", source=Product.Source.RETAIL)
        bulk = Product.objects.create(name="Плюмбус справочный", barcode="4600000000127", source=Product.Source.OFFBULK)

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ) as fetch:
            _run("--apply", "--sleep", "0", "--source", "off_bulk")

        bulk.refresh_from_db()
        assert bulk.calories_per_100g == 250
        assert fetch.call_count == 1, "сетевой товар трогать не должны были"

    def test_без_штрих_кода_не_берём(self):
        p = Product.objects.create(name="Плюмбус безымянный", source=Product.Source.OFF)

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=_off(kcal=250),
        ) as fetch:
            _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert fetch.call_count == 0

    def test_count_only_не_ходит_в_off(self):
        # Та же осторожность, что и в fill_kbju_ai: замер не должен ничего
        # запускать. Там на этом уже обожглись.
        _catalog("Плюмбус для счёта", "4600000000066")

        with patch("apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result") as fetch:
            out = _run("--count-only")

        assert fetch.call_count == 0
        assert "1" in out

    def test_нет_в_off_позиция_остаётся_пустой(self):
        p = _catalog("Плюмбус неизвестный", "4600000000073")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=({}, "not_found"),
        ):
            out = _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert "нет в OFF:           1" in out

    def test_молчащий_прогон_выглядит_как_зависший(self):
        # Так и вышло на проде: показ без записи печатал строку только по
        # найденной позиции, а когда не находилось ничего, команда молчала до
        # самого конца. Человек видит пустой экран и решает, что повисло.
        for i in range(30):
            _catalog(f"Плюмбус тихий {i}", f"46000002000{i:02d}")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=({}, "not_found"),
        ):
            out = _run("--sleep", "0")

        assert "…спрашиваю 1 из 30" in out
        assert "…спрашиваю 25 из 30" in out

    def test_просьбу_сбавить_темп_пережидаем(self):
        # MG_OFF429. На проде одиночная проверка получила 429 сразу после
        # прерванного замера: окно ещё не остыло. Повтор через две секунды его
        # не переживёт, а прогон осыплется в «не удалось спросить» на ровном
        # месте — хотя OFF в порядке и через минуту ответит.
        p = _catalog("Плюмбус притормозивший", "4600000000103")
        answers = [({}, "throttled"), ({}, "throttled"), (_off(kcal=250)[0], "ok")]

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            side_effect=answers,
        ):
            out = _run("--apply", "--sleep", "0")

        p.refresh_from_db()
        assert p.calories_per_100g == 250, "после ожидания позиция должна заполниться"
        assert "сбавить темп" in out
        assert "не удалось спросить: 0" in out

    def test_отказ_это_не_то_же_что_отсутствие(self):
        # Разница решающая на прогоне в восемнадцать тысяч позиций: если OFF
        # начнёт притормаживать, все отказы молча сложатся в «нет в OFF», итог
        # соврёт, а повторный прогон эти позиции уже не возьмёт — они будут
        # выглядеть проверенными.
        _catalog("Плюмбус недоспрошенный", "4600000000097")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=({}, "error"),
        ):
            out = _run("--apply", "--sleep", "0")

        assert "не удалось спросить: 1" in out
        assert "нет в OFF:           0" in out

    def test_череда_отказов_останавливает_прогон(self):
        # Двадцать подряд — это не «не повезло», а «нас больше не обслуживают».
        for i in range(30):
            _catalog(f"Плюмбус партии {i}", f"46000001000{i:02d}")

        with patch(
            "apps.fridge.management.commands.refill_kbju_from_off.fetch_off_result",
            return_value=({}, "error"),
        ) as fetch:
            out = _run("--apply", "--sleep", "0")

        assert "OFF не отвечает" in out
        # Три попытки на позицию, двадцать позиций — и остановка, а не все 30.
        assert fetch.call_count == 60


@pytest.mark.django_db
class TestМераДыр:
    def test_считает_дыры_и_делит_на_бесплатные_и_платные(self):
        _catalog("Плюмбус со штрихкодом", "4600000000080")
        Product.objects.create(name="Плюмбус без штрихкода", source=Product.Source.AUTO)
        Product.objects.create(
            name="Плюмбус с КБЖУ",
            source=Product.Source.AUTO,
            calories_per_100g=100,
            nutrition={"proteins": 1, "fats": 2, "carbs": 3},
        )

        out = StringIO()
        call_command("mg_kbju_gaps", stdout=out)
        text = out.getvalue()

        assert "бесплатно, refill_kbju_from_off" in text
        assert "платно, fill_kbju_ai" in text
        # Продукт с полным КБЖУ в дыры попасть не должен — иначе платная
        # починка пойдёт по тем, у кого всё и так есть.
        assert "Плюмбус с КБЖУ" not in text
