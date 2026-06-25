"""Тесты fill_kbju_ai с заглушкой AI-клиента (без сети)."""

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
    call_command("fill_kbju_ai", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.fixture
def clean_db(db):
    # убираем сид-продукты, чтобы чанк содержал только наши (детерминированные i)
    Product.objects.all().delete()


class TestFillKbjuAi:
    def test_fills_food_and_skips_non_food(self, clean_db, monkeypatch):
        food = Product.objects.create(name="Кабачок жареный", nutrition={})
        junk = Product.objects.create(name="Пакет фасовочный", nutrition={})
        _patch_ai(
            monkeypatch,
            '[{"i":0,"kcal":90,"protein":1.2,"fat":6.0,"carb":7.0},{"i":1,"food":false}]',
        )
        _run("--apply")
        food.refresh_from_db()
        junk.refresh_from_db()
        assert float(food.calories_per_100g) == 90
        assert food.nutrition["proteins"] == 1.2
        assert junk.nutrition == {}  # не еда — пропущено

    def test_dry_run_writes_nothing(self, clean_db, monkeypatch):
        p = Product.objects.create(name="Кабачок жареный", nutrition={})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":90,"protein":1.2,"fat":6.0,"carb":7.0}]')
        out = _run()  # без --apply
        p.refresh_from_db()
        assert p.nutrition == {}
        assert "DRY-RUN" in out

    def test_implausible_values_skipped(self, clean_db, monkeypatch):
        p = Product.objects.create(name="Что-то", nutrition={})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":99999,"protein":1,"fat":1,"carb":1}]')
        _run("--apply")
        p.refresh_from_db()
        assert p.nutrition == {}

    def test_skips_products_that_already_have_kbju(self, clean_db, monkeypatch):
        p = Product.objects.create(
            name="Гречка",
            calories_per_100g=343,
            nutrition={"calories": 343, "proteins": 12.6, "fats": 3.3, "carbs": 62.1},
        )
        # AI ответ не должен примениться — продукт не в выборке
        _patch_ai(monkeypatch, '[{"i":0,"kcal":1,"protein":1,"fat":1,"carb":1}]')
        _run("--apply")
        p.refresh_from_db()
        assert float(p.calories_per_100g) == 343
