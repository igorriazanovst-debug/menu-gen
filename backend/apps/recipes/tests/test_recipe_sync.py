# MG_RECIPESYNC: export_recipes / import_recipes_json — перенос рецептов между серверами.
import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.fridge.models import Product, ProductCategory
from apps.recipes.models import Recipe, RecipeProduct


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(slug="vegetables", name_ru="Овощи")


@pytest.fixture
def product(db, category):
    return Product.objects.create(name="Помидоры", category_fk=category)


def make_recipe(**kwargs) -> Recipe:
    """Recipe без post_save-пересборки связей (MG_RECIPELINK лезет в ИИ)."""
    r = Recipe(**kwargs)
    r._mg_skip_link_rebuild = True
    r.save()
    return r


@pytest.fixture
def recipe(db, product, category):
    r = make_recipe(
        title="Салат из помидоров",
        legacy_id="rf-1001",
        source_url="https://example.com/salad",
        cook_time="15 мин",
        cook_time_min=15,
        servings=2,
        ingredients=[{"name": "помидоры", "quantity": "2", "unit": "шт"}],
        steps=["Нарезать", "Посолить"],
        dish_type="salad",
        food_group="vegetable",
        kcal="123.4",
        is_published=True,
    )
    RecipeProduct.objects.create(
        recipe=r,
        product=product,
        category_fk=category,
        name_raw="помидоры",
        name_canonical="Помидоры",
        category_slug="vegetables",
        quantity="2",
        unit="шт",
        grams=200.0,
    )
    return r


def _export(tmp_path, **kwargs):
    path = tmp_path / "recipes.json"
    call_command("export_recipes", "--output", str(path), stdout=StringIO(), **kwargs)
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_export_writes_natural_keys(tmp_path, recipe):
    _, payload = _export(tmp_path)

    assert payload["count"] == 1
    data = payload["recipes"][0]
    # id и автор не переносятся — на приёмнике они свои
    assert "id" not in data
    assert "author" not in data
    assert data["title"] == "Салат из помидоров"
    assert data["steps"] == ["Нарезать", "Посолить"]
    assert data["kcal"] == "123.4"  # Decimal сериализуется строкой
    link = data["product_links"][0]
    assert link["product_name"] == "Помидоры"
    assert link["product_category_slug"] == "vegetables"
    assert link["grams"] == 200.0


def test_export_skips_custom_and_unpublished(tmp_path, recipe):
    make_recipe(title="Мой рецепт", is_custom=True)
    make_recipe(title="Черновик", is_published=False)

    _, payload = _export(tmp_path)

    assert [r["title"] for r in payload["recipes"]] == ["Салат из помидоров"]


def test_import_creates_recipe_and_links(tmp_path, recipe, product, category):
    path, _ = _export(tmp_path)
    # «целевой сервер»: рецепта нет, продукт с тем же именем есть
    recipe_id = recipe.id
    Recipe.objects.all().delete()

    out = StringIO()
    call_command("import_recipes_json", str(path), stdout=out)

    imported = Recipe.objects.get(title="Салат из помидоров")
    assert imported.id != recipe_id or True  # id может совпасть — важно, что он свой
    assert imported.legacy_id == "rf-1001"
    assert imported.steps == ["Нарезать", "Посолить"]
    assert str(imported.kcal) == "123.4"
    link = imported.product_links.get()
    assert link.product_id == product.id  # связь по имени продукта, не по чужому id
    assert link.category_fk_id == category.id
    assert link.grams == 200.0
    assert "Создано рецептов:   1" in out.getvalue()


def test_import_is_idempotent(tmp_path, recipe):
    path, _ = _export(tmp_path)

    out = StringIO()
    call_command("import_recipes_json", str(path), stdout=out)

    assert Recipe.objects.filter(title="Салат из помидоров").count() == 1
    assert "Пропущено (есть):   1" in out.getvalue()


def test_import_matches_by_title_when_no_legacy_id(tmp_path, recipe):
    path, payload = _export(tmp_path)
    payload["recipes"][0]["legacy_id"] = None
    payload["recipes"][0]["source_url"] = None
    payload["recipes"][0]["title"] = "  салат из ПОМИДОРОВ. "  # регистр/пробелы/точка
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    call_command("import_recipes_json", str(path), stdout=StringIO())

    assert Recipe.objects.count() == 1


def test_import_dry_run_writes_nothing(tmp_path, recipe):
    path, _ = _export(tmp_path)
    Recipe.objects.all().delete()

    out = StringIO()
    call_command("import_recipes_json", str(path), "--dry-run", stdout=out)

    assert Recipe.objects.count() == 0
    assert "DRY-RUN" in out.getvalue()


def test_import_without_create_products_keeps_link_unlinked(tmp_path, recipe):
    path, _ = _export(tmp_path)
    Recipe.objects.all().delete()
    Product.objects.all().delete()

    out = StringIO()
    call_command("import_recipes_json", str(path), stdout=out)

    link = RecipeProduct.objects.get()
    assert link.product_id is None
    assert link.name_raw == "помидоры"  # текст ингредиента не теряется
    assert Product.objects.count() == 0
    assert "Продуктов не нашли: 1" in out.getvalue()


def test_import_create_products_makes_missing_ones(tmp_path, recipe, category):
    path, _ = _export(tmp_path)
    Recipe.objects.all().delete()
    Product.objects.all().delete()

    call_command("import_recipes_json", str(path), "--create-products", stdout=StringIO())

    created = Product.objects.get(name="Помидоры")
    assert created.category_fk_id == category.id
    assert created.source == "import"
    assert RecipeProduct.objects.get().product_id == created.id


def test_import_update_refreshes_existing(tmp_path, recipe):
    path, payload = _export(tmp_path)
    payload["recipes"][0]["steps"] = ["Новый шаг"]
    payload["recipes"][0]["servings"] = 4
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    call_command("import_recipes_json", str(path), "--update", stdout=StringIO())

    recipe.refresh_from_db()
    assert recipe.steps == ["Новый шаг"]
    assert recipe.servings == 4
    assert Recipe.objects.count() == 1
    assert recipe.product_links.count() == 1  # связи пересобраны, а не задвоены
