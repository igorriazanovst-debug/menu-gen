"""MG_AUTOPROD: ингредиента нет в каталоге — заводим запись в каталоге.

Связь «ингредиент рецепта → продукт» строится по каталогу. Если продукта в нём
нет, сборка связей заводит его сама, иначе рецепт не найдётся в подборе «что
приготовить из холодильника».

Всё сломала загрузка справочников штрих-кодов: 32 тысячи конкретных упаковок
живут в той же таблице, но скрыты из подборщиков (`HIDDEN_FROM_PICKERS`).
Поиск «а нет ли уже такого продукта» шёл по всей таблице и потому:

- падал с MultipleObjectsReturned на одноимённых упаковках — прогон обрывался
  посреди базы, уже после того как отработал (платный) проход ИИ;
- а на единственном совпадении привязывал ингредиент к упаковке из
  справочника — к записи, которой нет ни в одном списке выбора.

Здесь проверяется и то и другое, плюс что своих дублей в каталоге не плодим.
"""

import pytest

from apps.fridge.models import Product, ProductCategory
from apps.recipes.recipe_products import _get_or_create_catalog_product


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(slug="veg", name_ru="Овощи", is_active=True)


@pytest.mark.django_db
class TestAutoProduct:
    def test_одноимённые_упаковки_не_ломают_прогон(self, category):
        """Две одноимённые записи в выгрузке OpenFoodFacts — обычное дело."""
        Product.objects.create(name="Мангодрин", barcode="4600000000017", source=Product.Source.OFFBULK)
        Product.objects.create(name="Мангодрин", barcode="4600000000024", source=Product.Source.OFFBULK)

        pid = _get_or_create_catalog_product("Мангодрин", category.id)

        assert Product.objects.get(pk=pid).source == Product.Source.AUTO

    def test_к_упаковке_из_справочника_не_привязываемся(self, category):
        """У справочной записи чужое КБЖУ и её нет в подборщиках."""
        pack = Product.objects.create(
            name="Крабсы хрустящие 200г", barcode="4600000000031", source=Product.Source.RETAIL
        )

        pid = _get_or_create_catalog_product("Крабсы хрустящие 200г", category.id)

        assert pid != pack.id
        assert Product.objects.get(pk=pid).source == Product.Source.AUTO

    def test_продукт_каталога_переиспользуется(self, category):
        """Второй рецепт с тем же ингредиентом не должен плодить запись."""
        existing = Product.objects.create(name="Топинамбурчик", source=Product.Source.MANUAL)

        assert _get_or_create_catalog_product("топинамбурчик", category.id) == existing.id
        assert Product.objects.filter(name__iexact="топинамбурчик").count() == 1

    def test_чужой_продукт_семьи_не_переиспользуется(self, category, django_user_model):
        """«Мамина настойка» одной семьи не должна попасть в чужие меню."""
        from apps.family.models import Family

        owner = django_user_model.objects.create_user(email="mama@example.com", password="pass12345", name="Мама")
        family = Family.objects.create(name="Ивановы", owner=owner)
        theirs = Product.objects.create(name="Мамина аджика", source=Product.Source.MANUAL, owner_family=family)

        pid = _get_or_create_catalog_product("Мамина аджика", category.id)

        assert pid != theirs.id
        assert Product.objects.get(pk=pid).owner_family is None

    def test_новый_продукт_получает_категорию(self, category):
        """Без категории запись не встанет в рубрикатор списка покупок."""
        pid = _get_or_create_catalog_product("Пастернакус", category.id)

        assert Product.objects.get(pk=pid).category_fk_id == category.id
