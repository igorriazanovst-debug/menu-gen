"""Тесты management-команды dedup_products (жёсткое слияние дублей)."""

from io import StringIO

from django.core.management import call_command

from apps.family.models import Family
from apps.fridge.models import FridgeItem, Product, ProductAlias
from apps.users.models import User


def _run(*args):
    out = StringIO()
    call_command("dedup_products", *args, stdout=out)
    return out.getvalue()


def _family():
    u = User.objects.create_user(email="h@e.com", name="U", password="x12345")
    return Family.objects.create(owner=u, name="F")


class TestDedupProducts:
    def test_alias_merge_repoints_and_deletes(self, db):
        canon = Product.objects.create(
            name="Огурцы", is_seed=True, calories_per_100g=15,
            nutrition={"calories": 15, "proteins": 0.8, "fats": 0.1, "carbs": 2.8},
        )
        dup = Product.objects.create(name="Огурец")  # авто-дубль без КБЖУ
        ProductAlias.objects.create(alias_norm="огурец", product=canon)
        fam = _family()
        fi = FridgeItem.objects.create(family=fam, name="огурец", product=dup)

        _run("--apply")

        assert not Product.objects.filter(name="Огурец").exists()
        assert Product.objects.filter(name="Огурцы").exists()
        fi.refresh_from_db()
        assert fi.product_id == canon.id
        # имя дубля стало синонимом канона
        assert ProductAlias.objects.filter(alias_norm="огурец", product=canon).exists()

    def test_same_normalized_name_merged(self, db):
        # «Творог» и «творог» — один и тот же продукт (нормализация совпадает)
        a = Product.objects.create(name="Творог")
        b = Product.objects.create(
            name="творог", calories_per_100g=121,
            nutrition={"calories": 121, "proteins": 17.2, "fats": 5.0, "carbs": 1.8},
        )
        _run("--apply")
        remaining = Product.objects.filter(name__iexact="творог")
        assert remaining.count() == 1
        # выжил тот, у кого есть КБЖУ
        assert remaining.first().id == b.id
        assert not Product.objects.filter(id=a.id).exists()

    def test_no_merge_for_distinct_products(self, db):
        Product.objects.create(name="Морковь")
        Product.objects.create(name="Капуста")
        _run("--apply")
        assert Product.objects.filter(name="Морковь").exists()
        assert Product.objects.filter(name="Капуста").exists()

    def test_dry_run_changes_nothing(self, db):
        canon = Product.objects.create(name="Огурцы", is_seed=True)
        dup = Product.objects.create(name="Огурец")
        ProductAlias.objects.create(alias_norm="огурец", product=canon)
        out = _run()  # без --apply
        assert Product.objects.filter(id=dup.id).exists()
        assert "DRY-RUN" in out
