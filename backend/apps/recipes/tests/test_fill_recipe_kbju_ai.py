"""Тесты fill_recipe_kbju_ai с заглушкой AI-клиента (без сети)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.recipes.models import Recipe


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
    call_command("fill_recipe_kbju_ai", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


_INGS = [{"name": "Кабачок", "grams": 200}, {"name": "Яйцо", "grams": 100}]


@pytest.mark.django_db
class TestFillRecipeKbjuAi:
    def test_fills_missing_and_writes_numeric_fields(self, monkeypatch):
        r = Recipe.objects.create(title="Оладьи из кабачков", ingredients=_INGS, nutrition={}, portion_g=150)
        _patch_ai(monkeypatch, '[{"i":0,"kcal":120,"protein":5.0,"fat":7.0,"carb":8.0,"sugar":2.0}]')
        _run("--apply")
        r.refresh_from_db()
        assert r.nutrition["calories"] == 120
        assert r.nutrition["proteins"] == 5.0
        assert r.nutrition["sugars"] == 2.0
        # числовые поля per-100g
        assert float(r.kcal_per_100g) == 120
        assert float(r.proteins_per_100g) == 5.0
        assert float(r.sugars_per_100g) == 2.0
        # per-порционные (portion_g=150): 120*1.5=180 ккал
        assert float(r.kcal) == 180

    def test_keeps_existing_values(self, monkeypatch):
        # calories уже есть, нет только жиров/углеводов → перезаписать calories нельзя
        r = Recipe.objects.create(title="Суп", ingredients=_INGS, nutrition={"calories": 50, "proteins": 3})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":120,"protein":9,"fat":4.0,"carb":6.0,"sugar":1.0}]')
        _run("--apply")
        r.refresh_from_db()
        assert r.nutrition["calories"] == 50  # не тронуто
        assert r.nutrition["proteins"] == 3  # не тронуто
        assert r.nutrition["fats"] == 4.0  # дозаполнено
        assert r.nutrition["carbs"] == 6.0  # дозаполнено

    def test_dry_run_writes_nothing(self, monkeypatch):
        r = Recipe.objects.create(title="Оладьи", ingredients=_INGS, nutrition={})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":120,"protein":5,"fat":7,"carb":8,"sugar":2}]')
        out = _run()
        r.refresh_from_db()
        assert r.nutrition == {}
        assert "DRY-RUN" in out

    def test_implausible_skipped(self, monkeypatch):
        r = Recipe.objects.create(title="Оладьи", ingredients=_INGS, nutrition={})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":99999,"protein":1,"fat":1,"carb":1,"sugar":0}]')
        _run("--apply")
        r.refresh_from_db()
        assert r.nutrition == {}

    def test_skips_recipe_without_ingredients(self, monkeypatch):
        r = Recipe.objects.create(title="Без состава", ingredients=[], nutrition={})
        _patch_ai(monkeypatch, '[{"i":0,"kcal":120,"protein":5,"fat":7,"carb":8,"sugar":2}]')
        out = _run("--apply")
        r.refresh_from_db()
        assert r.nutrition == {}
        assert "без ингредиентов" in out

    def test_skips_recipe_with_complete_kbju(self, monkeypatch):
        r = Recipe.objects.create(
            title="Готовый",
            ingredients=_INGS,
            nutrition={"calories": 100, "proteins": 5, "fats": 5, "carbs": 5},
        )
        _patch_ai(monkeypatch, '[{"i":0,"kcal":1,"protein":1,"fat":1,"carb":1,"sugar":1}]')
        _run("--apply")
        r.refresh_from_db()
        assert r.nutrition["calories"] == 100  # не в выборке, не тронуто
