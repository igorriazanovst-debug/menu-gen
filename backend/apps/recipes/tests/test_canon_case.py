"""MG_CANONCASE2: регистр канонизированного названия.

Модель отвечает Title Case, каталог написан иначе — «Лук репчатый». Первая
версия правила опускала в нижний регистр всё подряд, и на проде это испортило
бы шесть названий из восемнадцати: «Камамбер Vitalat» → «Камамбер vitalat».

Проверяется обе стороны правила: разнобой убирается, имя собственное остаётся.
Названия взяты с прода — там их и нашли.
"""

from apps.recipes.recipe_products import _clean_canon, _sentence_case


class TestSentenceCase:
    def test_title_case_becomes_catalog_style(self):
        assert _sentence_case("Сушеная Травка") == "Сушеная травка"
        assert _sentence_case("Сыр Твёрдый Любой") == "Сыр твёрдый любой"

    def test_all_caps_too(self):
        assert _sentence_case("ЯЙЦО КУРИНОЕ") == "Яйцо куриное"

    def test_first_letter_is_raised(self):
        assert _sentence_case("лук репчатый") == "Лук репчатый"

    def test_latin_word_is_left_alone(self):
        # Бренд, а не манера письма: «Камамбер vitalat» читается как опечатка.
        assert _sentence_case("Камамбер Vitalat") == "Камамбер Vitalat"
        assert _sentence_case("Паста Aroy-d карри") == "Паста Aroy-d карри"
        assert _sentence_case("Рис Arborio") == "Рис Arborio"

    def test_word_with_digit_is_left_alone(self):
        # «С1» — категория яйца, а не слово.
        assert _sentence_case("Яица - 1 шт. С1") == "Яица - 1 шт. С1"

    def test_quoted_word_is_left_alone(self):
        assert (
            _sentence_case('Кружки готового теста для вареников "Тестов"')
            == 'Кружки готового теста для вареников "Тестов"'
        )

    def test_rest_of_the_name_still_gets_lowered(self):
        # Латиница в одном слове не отменяет правило для остальных.
        assert _sentence_case("Соус Сладкий Чили Zero") == "Соус сладкий чили Zero"

    def test_empty_and_none_survive(self):
        assert _sentence_case("") == ""
        assert _sentence_case(None) == ""


class TestCleanCanonKeepsUsingTheRule:
    """Правило применяется там, где рождаются названия, — иначе оно бесполезно."""

    def test_percentage_stripped_and_case_fixed(self):
        assert _clean_canon("Сметана 20%") == "Сметана"
        assert _clean_canon("Молоко Топлёное") == "Молоко топлёное"

    def test_brand_survives_the_cleanup(self):
        assert _clean_canon("Соус сладкий чили Zero") == "Соус сладкий чили Zero"


class TestБрендКириллицей:
    """MG_BRANDCASE: «Свитлогорье» — бренд, а не прилагательное.

    Механические признаки имени собственного (латиница, цифра, кавычки) его не
    ловят, поэтому на dev правило предлагало «Пломбир Свитлогорье» → «Пломбир
    свитлогорье». Список брендов ведётся руками — отличить их может человек.
    """

    def test_бренд_сохраняет_заглавную(self):
        assert _sentence_case("Пломбир Свитлогорье") == "Пломбир Свитлогорье"

    def test_остальные_слова_строки_всё_так_же_понижаются(self):
        assert _sentence_case("Пломбир Ванильный Свитлогорье") == "Пломбир ванильный Свитлогорье"

    def test_ё_в_списке_не_мешает(self):
        assert _sentence_case("Пломбир Свитлогорьё") == "Пломбир Свитлогорьё"

    def test_бренд_первым_словом_остаётся_собой(self):
        assert _sentence_case("Свитлогорье пломбир") == "Свитлогорье пломбир"

    def test_не_бренд_понижается_как_прежде(self):
        assert _sentence_case("Пломбир Ванильный") == "Пломбир ванильный"
