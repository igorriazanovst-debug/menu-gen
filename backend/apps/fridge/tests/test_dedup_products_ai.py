"""Тесты dedup_products_ai с заглушкой AI-клиента (без сети)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.fridge.models import Product


class _StubAI:
    def __init__(self, response):
        self._response = response

    def complete(self, prompt, system="", max_tokens=256, temperature=0.0):
        return self._response


def _patch_ai(monkeypatch, response):
    import apps.common.ai_provider as ai

    monkeypatch.setattr(ai, "get_ai_client", lambda *a, **k: _StubAI(response))


def _run(*args):
    out = StringIO()
    call_command("dedup_products_ai", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.fixture
def clean_db(db):
    Product.objects.all().delete()


class TestDedupProductsAi:
    def test_merges_word_order_and_abbrev_variants(self, clean_db, monkeypatch):
        g1 = Product.objects.create(name="Йогурт греческий")
        g2 = Product.objects.create(name="Греческий йогурт")
        g3 = Product.objects.create(name="Греч. йогурт")
        plain = Product.objects.create(name="Йогурт")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Йогурт греческий"},{"i":1,"canon":"Йогурт греческий"},'
            '{"i":2,"canon":"Йогурт греческий"},{"i":3,"canon":"Йогурт"}]',
        )
        _run("--apply")
        # три греческих варианта схлопнулись в один (с каноничным именем)
        assert Product.objects.filter(id=g1.id).exists()
        assert not Product.objects.filter(id=g2.id).exists()
        assert not Product.objects.filter(id=g3.id).exists()
        # обычный йогурт — отдельный продукт
        assert Product.objects.filter(id=plain.id).exists()

    def test_distinct_varieties_not_merged(self, clean_db, monkeypatch):
        a = Product.objects.create(name="Творог 5%")
        b = Product.objects.create(name="Творог 9%")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Творог 5%"},{"i":1,"canon":"Творог 9%"}]',
        )
        _run("--apply")
        assert Product.objects.filter(id=a.id).exists()
        assert Product.objects.filter(id=b.id).exists()

    def test_dry_run_changes_nothing(self, clean_db, monkeypatch):
        g1 = Product.objects.create(name="Йогурт греческий")
        g2 = Product.objects.create(name="Греческий йогурт")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Йогурт греческий"},{"i":1,"canon":"Йогурт греческий"}]',
        )
        out = _run()  # без --apply
        assert Product.objects.filter(id=g1.id).exists()
        assert Product.objects.filter(id=g2.id).exists()
        assert "DRY-RUN" in out


class TestВыжившийВГруппе:
    """MG_DEDUPSURVIVOR: имя выжившего уезжает во все ссылки — и навсегда.

    Все случаи ниже взяты из плана, который команда выдала на dev на полном
    каталоге. Выбор выжившего смотрел на sid/КБЖУ, потом на совпадение с
    канон-формой и в конце на min(id) — и до канона дело обычно не доходило:

        «Сока лимона» -> «Лимонный ок»          (канон — «Лимонный сок»)
        «Куриного филе» -> «Курица (филе)»       (филе — не вся курица)
        «Масл подсолнечное» -> «Подсолнечное»    (канон — «Подсолнечное масло»)
        «Масла для обжарки» -> «Масла для жарки» (обрывок в обрывок)
        «Имбирь молотый сушеный» -> «Сушеного молотого имбиря»
    """

    def _plan(self, monkeypatch, response):
        _patch_ai(monkeypatch, response)
        return _run()

    def test_опечатка_в_имени_не_выигрывает(self, clean_db, monkeypatch):
        """Канон «Лимонный сок» — ни одно из имён им не является: не сливаем."""
        a = Product.objects.create(name="Сока лимона")
        b = Product.objects.create(name="Лимонный ок")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Лимонный сок"},{"i":1,"canon":"Лимонный сок"}]',
        )
        out = _run("--apply")

        assert Product.objects.filter(id=a.id).exists()
        assert Product.objects.filter(id=b.id).exists()
        assert "Пропущено групп" in out

    def test_уточнение_в_скобках_не_поглощает_обычную_запись(self, clean_db, monkeypatch):
        plain = Product.objects.create(name="Куриное филе")
        bracket = Product.objects.create(name="Курица (филе)")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Куриное филе"},{"i":1,"canon":"Куриное филе"}]',
        )
        _run("--apply")

        assert Product.objects.filter(id=plain.id).exists()
        assert Product.objects.filter(id=bracket.id).exists()

    def test_обрывок_имени_выжившим_не_становится(self, clean_db, monkeypatch):
        """«Подсолнечное» — не канон, канон «Подсолнечное масло». Сливать не во что."""
        a = Product.objects.create(name="Масл подсолнечное")
        b = Product.objects.create(name="Подсолнечное")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Подсолнечное масло"},{"i":1,"canon":"Подсолнечное масло"}]',
        )
        _run("--apply")

        assert Product.objects.filter(id=a.id).exists()
        assert Product.objects.filter(id=b.id).exists()

    def test_когда_канон_в_группе_есть_слияние_идёт_в_него(self, clean_db, monkeypatch):
        """Обратная сторона правила: пропускать всё подряд оно не должно."""
        typo = Product.objects.create(name="Масл подсолнечное")
        good = Product.objects.create(name="Подсолнечное масло")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Подсолнечное масло"},{"i":1,"canon":"Подсолнечное масло"}]',
        )
        _run("--apply")

        assert not Product.objects.filter(id=typo.id).exists()
        assert Product.objects.filter(id=good.id).exists()

    def test_примечание_и_количество_в_имени_выжившим_не_становятся(self, clean_db, monkeypatch):
        good = Product.objects.create(name="Яйца")
        junk = Product.objects.create(name="Яйца – 1 шт. с1")
        _patch_ai(monkeypatch, '[{"i":0,"canon":"Яйца"},{"i":1,"canon":"Яйца"}]')
        _run("--apply")

        assert Product.objects.filter(id=good.id).exists()
        assert not Product.objects.filter(id=junk.id).exists()

    def test_мусор_в_мусор_не_сливается(self, clean_db, monkeypatch):
        a = Product.objects.create(name="Масла для обжарки")
        b = Product.objects.create(name="Масла для жарки")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Растительное масло"},{"i":1,"canon":"Растительное масло"}]',
        )
        _run("--apply")

        assert Product.objects.filter(id=a.id).exists()
        assert Product.objects.filter(id=b.id).exists()

    def test_падежная_форма_уступает_именительной(self, clean_db, monkeypatch):
        nom = Product.objects.create(name="Имбирь молотый сушеный")
        gen = Product.objects.create(name="Сушеного молотого имбиря")
        _patch_ai(
            monkeypatch,
            '[{"i":0,"canon":"Имбирь молотый сушеный"},{"i":1,"canon":"Имбирь молотый сушеный"}]',
        )
        _run("--apply")

        assert Product.objects.filter(id=nom.id).exists()
        assert not Product.objects.filter(id=gen.id).exists()

    def test_в_плане_видны_идентификаторы(self, clean_db, monkeypatch):
        """Две записи с одинаковым именем в плане читаются как «само в себя»."""
        a = Product.objects.create(name="Филе грудки индейки")
        b = Product.objects.create(name="Филе грудки индейки")
        out = self._plan(
            monkeypatch,
            '[{"i":0,"canon":"Филе грудки индейки"},{"i":1,"canon":"Филе грудки индейки"}]',
        )

        assert f"#{a.id}" in out and f"#{b.id}" in out


class _StubByStage:
    """Отвечает по-разному на два вопроса команды: канон и выбор имени."""

    def __init__(self, canon, pick):
        self._canon = canon
        self._pick = pick

    def complete(self, prompt, system="", max_tokens=256, temperature=0.0):
        return self._pick if "best" in system else self._canon


def _patch_stages(monkeypatch, canon, pick):
    import apps.common.ai_provider as ai

    monkeypatch.setattr(ai, "get_ai_client", lambda *a, **k: _StubByStage(canon, pick))


class TestРазборПропущенныхГрупп:
    """MG_DEDUPPICK: у правила допуска есть своя цена, и её надо добирать.

    Канон приходит в единственном числе («яйцо», «огурец»), а в каталоге
    законно лежит множественное («Яйца», «Огурцы»). Совпадения нет ни у одного
    имени — и группа пропускается КАЖДЫЙ раз, сколько ни запускай. В списке
    покупок это ровно то, с чего всё началось: восемь строк про яйца, среди них
    «Яцо» и «Огурцs».
    """

    _CANON = '[{"i":0,"canon":"Плюмбус"},{"i":1,"canon":"Плюмбус"}]'

    def test_модель_выбирает_имя_из_группы(self, clean_db, monkeypatch):
        keep = Product.objects.create(name="Плюмбусы")
        gone = Product.objects.create(name="Плюмбусов")
        _patch_stages(monkeypatch, self._CANON, '[{"i":0,"best":"Плюмбусы"}]')

        out = _run("--apply")

        assert Product.objects.filter(id=keep.id).exists()
        assert not Product.objects.filter(id=gone.id).exists()
        assert "Разобрано вторым вопросом" in out

    def test_отказ_модели_оставляет_группу_нетронутой(self, clean_db, monkeypatch):
        a = Product.objects.create(name="Плюмбусы")
        b = Product.objects.create(name="Плюмбусов")
        _patch_stages(monkeypatch, self._CANON, '[{"i":0,"best":null}]')

        out = _run("--apply")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2
        assert "Пропущено групп" in out

    def test_сочинённое_имя_не_принимается(self, clean_db, monkeypatch):
        """Выбор идёт из готовых имён: записи с чужим именем в группе нет."""
        a = Product.objects.create(name="Плюмбусы")
        b = Product.objects.create(name="Плюмбусов")
        _patch_stages(monkeypatch, self._CANON, '[{"i":0,"best":"Плюмбус обыкновенный"}]')

        _run("--apply")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2

    def test_обрывок_выжившим_не_становится_и_здесь(self, clean_db, monkeypatch):
        a = Product.objects.create(name="Плюмбусы – 1 шт. с1")
        b = Product.objects.create(name="Плюмбусов")
        _patch_stages(monkeypatch, self._CANON, '[{"i":0,"best":"Плюмбусы – 1 шт. с1"}]')

        _run("--apply")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2

    def test_потерянная_пачка_не_выдаётся_за_отказ(self, clean_db, monkeypatch):
        """На dev в «пропущено» стояло 13 групп, но десять были целой потерянной пачкой.

        Читалось это как решение модели, хотя она их не видела. Исходы разные:
        отказ окончателен, обрыв лечится повтором.
        """
        Product.objects.create(name="Плюмбусы")
        Product.objects.create(name="Плюмбусов")

        class _Broken(_StubByStage):
            def complete(self, prompt, system="", max_tokens=256, temperature=0.0):
                if "best" in system:
                    raise RuntimeError("Read timed out")
                return self._canon

        import apps.common.ai_provider as ai

        monkeypatch.setattr(ai, "get_ai_client", lambda *a, **k: _Broken(self._CANON, ""))

        out = _run()

        assert "До модели не дошло групп: 1" in out
        assert "Пропущено групп" not in out

    def test_вторая_попытка_добирает_потерянное(self, clean_db, monkeypatch):
        keep = Product.objects.create(name="Плюмбусы")
        gone = Product.objects.create(name="Плюмбусов")

        class _FlakyOnce(_StubByStage):
            tries = 0

            def complete(self, prompt, system="", max_tokens=256, temperature=0.0):
                if "best" not in system:
                    return self._canon
                _FlakyOnce.tries += 1
                # Первый проход рвётся, вторым та же группа доходит. Ошибка
                # намеренно не AIRequestError: complete_with_retry повторяет
                # только её, так что пачка теряется целиком — как на dev.
                if _FlakyOnce.tries == 1:
                    raise RuntimeError("Read timed out")
                return self._pick

        import apps.common.ai_provider as ai

        monkeypatch.setattr(ai, "get_ai_client", lambda *a, **k: _FlakyOnce(self._CANON, '[{"i":0,"best":"Плюмбусы"}]'))

        _run("--apply")

        assert Product.objects.filter(id=keep.id).exists()
        assert not Product.objects.filter(id=gone.id).exists()

    def test_флагом_второй_вопрос_отключается(self, clean_db, monkeypatch):
        a = Product.objects.create(name="Плюмбусы")
        b = Product.objects.create(name="Плюмбусов")
        _patch_stages(monkeypatch, self._CANON, '[{"i":0,"best":"Плюмбусы"}]')

        out = _run("--apply", "--no-resolve")

        assert Product.objects.filter(id__in=[a.id, b.id]).count() == 2
        assert "Разобрано вторым вопросом" not in out


class TestПредупреждениеПроСрез:
    """MG_DEDUPLIMIT: срез по id рвёт пары, и пустой план читается как «дублей нет».

    На проде --limit 200 не нашёл ни одного дубля среди яиц: «Яйца куриные» (41)
    и «Яичный белок» (197) в срез попали, а «Белок» (1018) и «Яцо» (2034) — нет.

    Рубрика решается для каждой записи отдельно, и срез там честен. Дубль
    решается парой — тут срез меняет ответ.
    """

    def test_срез_сопровождается_предупреждением(self, db):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command

        out, err = StringIO(), StringIO()
        with (
            mock.patch(
                "apps.fridge.management.commands.dedup_products_ai.complete_with_retry",
                return_value="[]",
            ),
            mock.patch("apps.common.ai_provider.get_batch_ai_client"),
            mock.patch("apps.common.ai_provider.check_ai_available"),
        ):
            call_command("dedup_products_ai", "--limit", "5", stdout=out, stderr=err)

        text = err.getvalue()
        assert "не в этом срезе" in text
        assert "без --limit" in text
