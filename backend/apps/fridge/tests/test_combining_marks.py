"""MG_COMBINING: «й» бывает не «й».

В каталоге на проде жила запись #1803 «Яйцо», записанная пятью символами:
«Я», «и», U+0306 (комбинирующая кратка), «ц», «о». Выглядит неотличимо, но это
другая строка — и потому она не совпадала ни с чем:

- поиск по имени её не находил (и я решил, что записи нет);
- дедуп не собирал её в группу с «Яйца куриные»;
- ингредиент рецепта по имени на неё не наводился.

Итог — невидимая запись каталога, дающая отдельную строку «Яйцо» в каждом
списке покупок рядом с «Яйца куриные». Приезжает такое из скачанных рецептов
регулярно, так что чинить надо сравнение, а не одну запись.
"""

import pytest

from apps.fridge.aliases import normalize_alias
from apps.fridge.models import Product, ProductAlias
from apps.recipes.recipe_products import _sentence_case

# «Яйцо» через «и» + U+0306 — ровно то, что лежало в каталоге.
BROKEN = "\u042f\u0438\u0306\u0446\u043e"
GOOD = "Яйцо"


class TestСравнениеИмён:
    def test_составной_знак_на_ключ_не_влияет(self):
        assert BROKEN != GOOD  # строки разные — в этом вся беда
        assert normalize_alias(BROKEN) == normalize_alias(GOOD)

    def test_ключ_получается_обычный(self):
        assert normalize_alias(BROKEN) == "яйцо"

    def test_одинокий_знак_в_ключ_не_попадает(self):
        """Кратке, которой не с чем соединяться, в ключе сравнения делать нечего."""
        assert normalize_alias("\u0421\u043e\u043b\u044c\u0306") == "соль"

    def test_обычные_имена_не_меняются(self):
        assert normalize_alias("Лук репчатый") == "лук репчатый"
        assert normalize_alias("Сливки 10%") == "сливки 10%"


class TestЗаписьИмени:
    def test_имя_приводится_к_составленной_форме(self):
        out = _sentence_case(BROKEN)

        assert out == GOOD
        assert len(out) == 4

    def test_остальное_правило_не_ломается(self):
        assert _sentence_case("Сушеная Травка") == "Сушеная травка"
        assert _sentence_case("Рис Arborio") == "Рис Arborio"


@pytest.mark.django_db
class TestПоискНаходитЗапись:
    def test_ингредиент_наводится_на_битую_запись(self):
        """До правки такая запись была невидимой: ингредиент её не находил."""
        from apps.fridge.aliases import product_ref_index, resolve_ref

        product = Product.objects.create(name="\u041f\u043b\u044e\u0438\u0306\u043c\u0431\u0443\u0441")

        ref = resolve_ref("Плюймбус", product_ref_index())

        assert ref is not None
        assert ref["id"] == product.id

    def test_синоним_с_составным_знаком_находится(self):
        """Имя выдуманное: синоним «яйцо» посевная миграция заводит сама."""
        from apps.fridge.aliases import product_ref_index, resolve_ref

        product = Product.objects.create(name="Плюмбус обычный")
        ProductAlias.objects.create(
            alias_norm=normalize_alias("\u041f\u043b\u044e\u0438\u0306\u043c\u0431\u0443\u0441"),
            product=product,
            source="manual",
        )

        assert resolve_ref("Плюймбус", product_ref_index())["id"] == product.id
