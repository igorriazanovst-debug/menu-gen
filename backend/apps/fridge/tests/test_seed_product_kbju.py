"""Тесты management-команды seed_product_kbju (КБЖУ сид-продуктам)."""

from io import StringIO

from django.core.management import call_command

from apps.fridge.models import Product


def _run(*args):
    out = StringIO()
    call_command("seed_product_kbju", *args, stdout=out)
    return out.getvalue()


class TestSeedProductKbju:
    def test_fills_empty_seed_product(self, db):
        p = Product.objects.create(name="Гречка", nutrition={})
        _run()
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 343
        assert p.nutrition["proteins"] == 12.6
        assert p.nutrition["fats"] == 3.3
        assert p.nutrition["carbs"] == 62.1
        assert p.nutrition["calories"] == 343

    def test_matching_is_case_and_yo_insensitive(self, db):
        # «ё» -> «е», регистр не важен
        p = Product.objects.create(name="свЕкла", nutrition={})
        _run()
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 43

    def test_skips_product_with_existing_nutrition(self, db):
        # реальные данные (напр. из скана штрихкода) не затираем
        p = Product.objects.create(
            name="Молоко",
            calories_per_100g=99,
            nutrition={"calories": 99, "proteins": 9, "fats": 9, "carbs": 9},
        )
        _run()
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 99
        assert p.nutrition["proteins"] == 9

    def test_force_overwrites_existing_nutrition(self, db):
        p = Product.objects.create(
            name="Молоко",
            calories_per_100g=99,
            nutrition={"calories": 99, "proteins": 9, "fats": 9, "carbs": 9},
        )
        _run("--force")
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 52
        assert p.nutrition["proteins"] == 2.8

    def test_unmatched_product_untouched(self, db):
        p = Product.objects.create(name="Несуществующий продукт XYZ", nutrition={})
        _run()
        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert p.nutrition == {}

    def test_dry_run_does_not_save(self, db):
        p = Product.objects.create(name="Рис", nutrition={})
        out = _run("--dry-run")
        p.refresh_from_db()
        assert p.calories_per_100g is None
        assert p.nutrition == {}
        assert "DRY-RUN" in out
