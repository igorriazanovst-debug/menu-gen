"""MG_AUTOPROD2: разбор того, что машина уже насыпала в каталог.

Записи `source=auto` заводит сборка связей рецепт→продукт, и в подборщиках они
видны наравне с выверенными. За несколько импортов туда натекло то, что едой не
является: разметка страницы рецепта («Время приготовления 40 мин», «Итальянская
кухня») и названия блюд, стоявшие в исходнике в списке ингредиентов.

Первая версия команды сносила всё машинное из «Прочего» — и забирала вместе с
мусором «Бекон копчёный» и «Соль мелкую». Поэтому проверять здесь надо не
«удалилось ли», а границы: что считается мусором и чего команда не трогает.
"""

import pytest
from django.core.management import call_command

from apps.fridge.management.commands.mg_prune_auto_products import is_metadata
from apps.fridge.models import Product, ProductAlias, ProductCategory
from apps.recipes.models import Recipe, RecipeProduct


@pytest.fixture
def cats(db):
    other, _ = ProductCategory.objects.get_or_create(slug="other", defaults={"name_ru": "Прочее", "is_active": True})
    fruit, _ = ProductCategory.objects.get_or_create(slug="fruit", defaults={"name_ru": "Фрукты", "is_active": True})
    return other, fruit


@pytest.fixture
def auto(cats):
    other, _fruit = cats

    def _make(name):
        return Product.objects.create(name=name, source=Product.Source.AUTO, category_fk=other)

    return _make


def run(rules="metadata", apply=True):
    call_command("mg_prune_auto_products", rules=rules, **({"apply": True} if apply else {}))


class TestMetadataRule:
    """Правило работает по названию, база для этого не нужна."""

    @pytest.mark.parametrize(
        "name",
        [
            "Время приготовления 40 мин",
            "40 мин",
            "Итальянская кухня",
            "Завтрак",
            "Выше",
            "Очищенный",
            "Чёрный",
            "Вегетарианские",
        ],
    )
    def test_разметка_страницы_это_мусор(self, name):
        assert is_metadata(name) is True

    @pytest.mark.parametrize("name", ["Бекон копчёный", "Соль мелкая", "Морской коктейль", "Хлопья темпура"])
    def test_настоящий_продукт_не_мусор(self, name):
        assert is_metadata(name) is False

    @pytest.mark.parametrize("name", ["Мороженое", "Заливное", "Жаркое"])
    def test_прилагательное_бывает_продуктом(self, name):
        """По форме прилагательное, по смыслу еда — окончания -ое/-ее не трогаем."""
        assert is_metadata(name) is False


@pytest.mark.django_db
class TestPrune:
    def test_разметка_удаляется(self, auto):
        junk = auto("Время приготовления 40 мин")

        run()

        assert not Product.objects.filter(pk=junk.pk).exists()

    def test_блюдо_по_умолчанию_не_трогаем(self, auto):
        """Совпадение с рецептом не доказывает, что продукта не существует.

        «Багет» есть и в рецептах, и на полке магазина. Правило dish на проверке
        забирало шесть таких из десяти, поэтому по умолчанию оно выключено.
        """
        Recipe.objects.create(title="Багет")
        product = auto("Багет")

        run()

        assert Product.objects.filter(pk=product.pk).exists()

    def test_правило_dish_включается_руками(self, auto):
        """Для явного разбора коротких списков правило всё же нужно."""
        Recipe.objects.create(title="Рататуй")
        dish = auto("Рататуй")

        run(rules="metadata,dish")

        assert not Product.objects.filter(pk=dish.pk).exists()

    def test_продукт_из_прочего_остаётся(self, auto):
        """«Прочее» — не метка ошибки: соль и бекон просто не разложились."""
        good = auto("Бекон копчёный")

        run()

        assert Product.objects.filter(pk=good.pk).exists()

    def test_без_apply_ничего_не_трогаем(self, auto):
        junk = auto("Итальянская кухня")

        run(apply=False)

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_правило_all_забирает_всё(self, auto):
        """Широкий отбор остался, но включается только руками."""
        good = auto("Бекон копчёный")

        run(rules="all")

        assert not Product.objects.filter(pk=good.pk).exists()

    def test_неизвестное_правило_ничего_не_делает(self, auto):
        junk = auto("Итальянская кухня")

        run(rules="metdata")

        assert Product.objects.filter(pk=junk.pk).exists()


@pytest.mark.django_db
class TestUntouchable:
    def test_продукт_из_холодильника_не_трогаем(self, auto, django_user_model):
        """Машинный он или нет, но им пользуются."""
        from apps.family.models import Family
        from apps.fridge.models import FridgeItem

        junk = auto("Итальянская кухня")
        owner = django_user_model.objects.create_user(email="u@example.com", password="pass12345", name="У")
        family = Family.objects.create(name="Семья", owner=owner)
        FridgeItem.objects.create(family=family, product=junk, name=junk.name, quantity=1)

        run()

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_продукт_с_синонимом_не_трогаем(self, auto):
        """Синоним заводит редактор — значит запись уже разобрали руками."""
        junk = auto("Итальянская кухня")
        ProductAlias.objects.create(product=junk, alias_norm="итальянская кухня")

        run()

        assert Product.objects.filter(pk=junk.pk).exists()

    def test_выверенный_продукт_не_трогаем(self, cats):
        """source=manual — завёл человек, категория тут ни при чём."""
        other, _fruit = cats
        mine = Product.objects.create(name="Итальянская кухня", source=Product.Source.MANUAL, category_fk=other)

        run()

        assert Product.objects.filter(pk=mine.pk).exists()

    def test_рубрика_от_правила_по_имени_больше_не_защищает(self, cats):
        """MG_PRUNEWIDE: раньше здесь проверялось обратное, и на то была причина.

        Пока рубрики стояли у немногих, наличие рубрики означало, что сегмент
        разобрал канонизатор, — и правило по имени такую запись не трогало.
        Потом рубрики проставили всем подряд отдельным прогоном на 284 записи,
        и основание исчезло: «Кусочки трески по 90г» получили рубрику «Рыба» не
        потому, что кто-то признал их продуктом.

        «Чёрный» — обрывок строки в любой рубрике.
        """
        _other, fruit = cats
        junk = Product.objects.create(name="Чёрный", source=Product.Source.AUTO, category_fk=fruit)

        run()

        assert not Product.objects.filter(pk=junk.pk).exists()

    def test_связь_рецепта_переживает_удаление(self, auto):
        """Список покупок берёт название и категорию из самой связи."""
        junk = auto("Время приготовления 40 мин")
        recipe = Recipe.objects.create(title="Салат")
        RecipeProduct.objects.create(
            recipe=recipe,
            product=junk,
            name_raw="время приготовления 40 мин",
            name_canonical="Время приготовления 40 мин",
            category_slug="other",
        )

        run()

        link = RecipeProduct.objects.get(recipe=recipe)
        assert link.product_id is None
        assert link.name_canonical == "Время приготовления 40 мин"


@pytest.mark.django_db
class TestOrphanRule:
    """Записи, на которые не ссылается вообще ничто.

    Остаются после пересборки связей: связи ушли на правильные продукты, а то,
    что завёл прошлый прогон по сырому названию, повисло. Правило смотрит только
    на ссылки, поэтому берёт и то, чего не поймать по названию, — «Мандарина».
    """

    def test_запись_без_единой_ссылки_удаляется(self, auto):
        stale = auto("Мандарина")

        run(rules="orphan")

        assert not Product.objects.filter(pk=stale.pk).exists()

    def test_связь_рецепта_здесь_считается(self, auto):
        """В остальных правилах ею пренебрегают, тут — нет: на запись ссылаются."""
        used = auto("Мандарин")
        recipe = Recipe.objects.create(title="Компот")
        RecipeProduct.objects.create(recipe=recipe, product=used, name_raw="мандарин")

        run(rules="orphan")

        assert Product.objects.filter(pk=used.pk).exists()

    def test_категория_и_название_роли_не_играют(self, cats):
        """Правило про ссылки, а не про текст: годная «Слива» без ссылок тоже уйдёт."""
        _other, fruit = cats
        good_name = Product.objects.create(name="Слива", source=Product.Source.AUTO, category_fk=fruit)

        run(rules="orphan")

        assert not Product.objects.filter(pk=good_name.pk).exists()

    def test_выверенный_продукт_не_трогаем(self, cats):
        other, _fruit = cats
        mine = Product.objects.create(name="Мамина аджика", source=Product.Source.MANUAL, category_fk=other)

        run(rules="orphan")

        assert Product.objects.filter(pk=mine.pk).exists()

    def test_продукт_из_холодильника_не_трогаем(self, auto, django_user_model):
        from apps.family.models import Family
        from apps.fridge.models import FridgeItem

        stale = auto("Мандарина")
        owner = django_user_model.objects.create_user(email="o@example.com", password="pass12345", name="О")
        family = Family.objects.create(name="Семья", owner=owner)
        FridgeItem.objects.create(family=family, product=stale, name=stale.name, quantity=1)

        run(rules="orphan")

        assert Product.objects.filter(pk=stale.pk).exists()


@pytest.mark.django_db
class TestNoiseRule:
    """MG_NOTENOISE: в каталоге осели названия с примечанием и количеством.

    Примеры взяты с прода: «Масло для обжарки», «Зелень укропа 4-5 веточек для
    подачи», «Апельсин ~200 г», «3 яйца вареных», «Сливочное масло 72». Продукт
    в такой строке может и быть, но в общем каталоге под этим именем ему не
    место — правило пользуется тем же фильтром, что и сборка связей.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "Масло для обжарки",
            "Зелень укропа 4-5 веточек для подачи",
            "Апельсин ~200 г",
            "3 яйца вареных",
            "Сливочное масло 72",
            "Соль по вкусу",
        ],
    )
    def test_мусорное_имя_удаляется(self, auto, name):
        p = auto(name)

        run(rules="noise")

        assert not Product.objects.filter(id=p.id).exists()

    @pytest.mark.parametrize(
        "name",
        [
            "Сливки 10%",
            "Творог 5%",
            "Морковь по-корейски",
            "Крабовые палочки",
            "Сыр твёрдый любой",
        ],
    )
    def test_нормальное_имя_остаётся(self, auto, name):
        p = auto(name)

        run(rules="noise")

        assert Product.objects.filter(id=p.id).exists()

    def test_правило_не_включено_по_умолчанию(self, auto):
        p = auto("Масло для обжарки")

        run()

        assert Product.objects.filter(id=p.id).exists()

    def test_живую_запись_правило_не_трогает(self, auto, cats):
        """Ссылка откуда угодно, кроме связи рецепта, означает, что запись нужна."""
        p = auto("Масло для обжарки")
        ProductAlias.objects.create(product=p, alias_norm="масло жарочное", source="manual")

        run(rules="noise")

        assert Product.objects.filter(id=p.id).exists()


@pytest.mark.django_db
class TestОбластьПравил:
    """MG_PRUNEWIDE: мусор по имени ищется во всех рубриках, а не только в «Прочем».

    Пока рубрик почти ни у кого не было, «Прочее» и было областью мусора. После
    раскладки рубрик мусор разъехался по разделам и стал команде невидим:
    «Кусочки трески по 90г» нашлись в «Рыбе» случайно, при разборе связей.

    Правила по названию (metadata, noise) от рубрики не зависят и потому
    смотрят весь машинный каталог. Правила dish и all судят иначе, и их
    безопасность держится на узкой области — им «Прочее» и остаётся.
    """

    @pytest.fixture
    def in_fish(self, db):
        fish, _ = ProductCategory.objects.get_or_create(
            slug="fish", defaults={"name_ru": "Рыба и морепродукты", "is_active": True}
        )

        def _make(name):
            return Product.objects.create(name=name, source=Product.Source.AUTO, category_fk=fish)

        return _make

    def test_обрывок_в_обычной_рубрике_удаляется(self, in_fish):
        p = in_fish("Кусочки плюмбуса по 90г")

        run(rules="noise")

        assert not Product.objects.filter(id=p.id).exists()

    def test_разметка_в_обычной_рубрике_удаляется(self, in_fish):
        p = in_fish("Время приготовления 40 мин")

        run(rules="metadata")

        assert not Product.objects.filter(id=p.id).exists()

    def test_правило_all_дальше_прочего_не_идёт(self, in_fish):
        """Оно сносит всё машинное подряд — вот его и держим в узкой области."""
        p = in_fish("Плюмбус обыкновенный")

        run(rules="all")

        assert Product.objects.filter(id=p.id).exists()

    def test_правило_dish_дальше_прочего_не_идёт(self, in_fish):
        Recipe.objects.create(title="Плюмбус в духовке")
        p = in_fish("Плюмбус в духовке")

        run(rules="dish")

        assert Product.objects.filter(id=p.id).exists()

    def test_живую_запись_не_трогаем_и_в_обычной_рубрике(self, in_fish):
        p = in_fish("Кусочки плюмбуса по 90г")
        ProductAlias.objects.create(product=p, alias_norm="плюмбусные кусочки", source="manual")

        run(rules="noise")

        assert Product.objects.filter(id=p.id).exists()
