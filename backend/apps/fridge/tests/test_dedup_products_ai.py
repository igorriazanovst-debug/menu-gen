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
