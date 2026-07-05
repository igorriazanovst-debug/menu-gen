# MG_501_V_tests
"""MG-501 tests: новые поля Recipe + сериализаторы."""

from decimal import Decimal

import pytest

from apps.recipes.models import Recipe


@pytest.mark.django_db
class TestMG501Model:
    def test_cooking_method_choices(self):
        assert Recipe.CookingMethod.BOILED == "boiled"
        assert Recipe.CookingMethod.BAKED == "baked"
        assert Recipe.CookingMethod.FRIED == "fried"
        assert Recipe.CookingMethod.GRILLED == "grilled"
        assert Recipe.CookingMethod.RAW == "raw"
        assert Recipe.CookingMethod.STEWED == "stewed"
        assert Recipe.CookingMethod.STEAMED == "steamed"

    def test_create_with_new_fields(self):
        r = Recipe.objects.create(
            title="Тестовое блюдо",
            cooking_method=Recipe.CookingMethod.BAKED,
            has_added_sugar=False,
            oil_tsp=Decimal("1.5"),
            serving_size_label="1 тарелка / 200 г",
        )
        r.refresh_from_db()
        assert r.cooking_method == "baked"
        assert r.has_added_sugar is False
        assert r.oil_tsp == Decimal("1.5")
        assert r.serving_size_label == "1 тарелка / 200 г"

    def test_defaults(self):
        r = Recipe.objects.create(title="Без классификации")
        r.refresh_from_db()
        assert r.cooking_method is None
        assert r.has_added_sugar is False
        assert r.oil_tsp is None
        assert r.serving_size_label is None


@pytest.mark.django_db
class TestMG501Serializers:
    def test_list_serializer_has_new_fields(self):
        from apps.recipes.serializers import RecipeListSerializer

        r = Recipe.objects.create(
            title="ListTest",
            cooking_method="grilled",
            has_added_sugar=True,
            oil_tsp=Decimal("2.0"),
            serving_size_label="1 шт",
        )
        data = RecipeListSerializer(r).data
        for f in ("cooking_method", "has_added_sugar", "oil_tsp", "serving_size_label"):
            assert f in data, f"List serializer должен содержать {f}"
        assert data["cooking_method"] == "grilled"
        assert data["has_added_sugar"] is True
        assert data["serving_size_label"] == "1 шт"

    def test_detail_serializer_has_new_fields(self):
        from apps.recipes.serializers import RecipeDetailSerializer

        r = Recipe.objects.create(title="DetailTest")
        data = RecipeDetailSerializer(r).data
        for f in ("cooking_method", "has_added_sugar", "oil_tsp", "serving_size_label"):
            assert f in data

    def test_write_serializer_creates_with_new_fields(self):
        from apps.recipes.serializers import RecipeWriteSerializer

        class _Req:
            pass

        req = _Req()
        # минимально: создать пользователя для author
        from apps.users.models import User

        u, _ = User.objects.get_or_create(name="WriteTest", defaults={"email": "wt@dev.local"})
        req.user = u

        ser = RecipeWriteSerializer(
            data={
                "title": "Новое блюдо",
                "ingredients": [{"name": "вода"}],
                "steps": [{"text": "налить"}],
                "nutrition": {},
                "categories": [],
                "cooking_method": "stewed",
                "has_added_sugar": True,
                "oil_tsp": "0.5",
                "serving_size_label": "стакан",
            },
            context={"request": req},
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        assert obj.cooking_method == "stewed"
        assert obj.has_added_sugar is True
        assert obj.oil_tsp == Decimal("0.5")
        assert obj.serving_size_label == "стакан"
