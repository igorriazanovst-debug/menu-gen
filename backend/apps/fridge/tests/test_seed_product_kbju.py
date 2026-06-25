"""Тесты management-команды seed_product_kbju (КБЖУ + базовые продукты + синонимы)."""

from io import StringIO

from django.core.management import call_command
from rest_framework.test import APIClient

from apps.fridge.models import Product, ProductAlias
from apps.users.models import User


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
        p = Product.objects.create(name="свЕкла", nutrition={})
        _run()
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 43

    def test_skips_product_with_existing_nutrition(self, db):
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

    def test_creates_missing_base_product(self, db):
        # «Миндаль» нет в сидах — команда должна его создать с КБЖУ.
        assert not Product.objects.filter(name="Миндаль").exists()
        _run()
        p = Product.objects.get(name="Миндаль")
        assert float(p.calories_per_100g) == 575
        assert p.nutrition["proteins"] == 18.6
        assert p.is_seed is True

    def test_creates_alias_for_synonym(self, db):
        Product.objects.create(name="Огурцы", nutrition={})
        _run()
        assert ProductAlias.objects.filter(alias_norm="огурец").exists()


class TestAliasSearch:
    """Поиск по синонимам через ProductSearchView (ед./мн. число)."""

    def _auth(self):
        u = User.objects.create_user(email="u@e.com", name="U", password="x12345")
        c = APIClient()
        c.force_authenticate(user=u)
        return c

    def test_singular_finds_plural_seed_product(self, db):
        Product.objects.create(name="Огурцы", nutrition={})
        _run()
        c = self._auth()
        resp = c.get("/api/v1/fridge/products/search/", {"q": "огурец"})
        assert resp.status_code == 200
        names = [r["name"] for r in resp.data["results"]]
        assert "Огурцы" in names

    def test_substring_still_works(self, db):
        Product.objects.create(name="Огурцы", nutrition={})
        _run()
        c = self._auth()
        resp = c.get("/api/v1/fridge/products/search/", {"q": "Огур"})
        names = [r["name"] for r in resp.data["results"]]
        assert "Огурцы" in names
