# MG_603_V_tests
"""
MG-603: unit-покрытие apps/recipes/serializers.py.

Missing lines до патча:
 91          validate_ingredients: value не list
 99, 102     validate_steps: не list / без 'text'
 106-116     validate_suitable_for целиком
 122         validate.get_val: name in attrs
 127         food_group=grain без grain_type
 131         food_group=protein без protein_type
"""
import pytest

from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeWriteSerializer


def _minimal(**overrides):
    """Минимально валидные данные для RecipeWriteSerializer."""
    data = {
        "title": "Тест",
        "ingredients": [{"name": "ингр", "quantity": "100", "unit": "г"}],
        "steps": [{"text": "Шаг 1"}],
        "nutrition": {},
        "categories": [],
    }
    data.update(overrides)
    return data


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ validate_ingredients (строка 91)                                        ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestValidateIngredients:
    def test_not_list_raises(self):
        s = RecipeWriteSerializer(data=_minimal(ingredients="not a list"))
        assert s.is_valid() is False
        assert "ingredients" in s.errors

    def test_item_without_name_raises(self):
        s = RecipeWriteSerializer(data=_minimal(
            ingredients=[{"quantity": "100", "unit": "г"}]
        ))
        assert s.is_valid() is False
        assert "ingredients" in s.errors

    def test_item_not_dict_raises(self):
        s = RecipeWriteSerializer(data=_minimal(ingredients=["just a string"]))
        assert s.is_valid() is False
        assert "ingredients" in s.errors

    def test_valid_ingredients(self):
        s = RecipeWriteSerializer(data=_minimal())
        assert s.is_valid(), s.errors


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ validate_steps (строки 99, 102)                                         ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestValidateSteps:
    def test_not_list_raises(self):
        s = RecipeWriteSerializer(data=_minimal(steps="not a list"))
        assert s.is_valid() is False
        assert "steps" in s.errors

    def test_item_without_text_raises(self):
        s = RecipeWriteSerializer(data=_minimal(steps=[{"order": 1}]))
        assert s.is_valid() is False
        assert "steps" in s.errors

    def test_item_not_dict_raises(self):
        s = RecipeWriteSerializer(data=_minimal(steps=["просто строка"]))
        assert s.is_valid() is False
        assert "steps" in s.errors


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ validate_suitable_for (строки 106-116)                                  ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestValidateSuitableFor:
    def test_empty_string_returns_empty_list(self):
        s = RecipeWriteSerializer(data=_minimal(suitable_for=""))
        assert s.is_valid(), s.errors
        assert s.validated_data.get("suitable_for") == []

    def test_not_list_raises(self):
        s = RecipeWriteSerializer(data=_minimal(suitable_for="breakfast"))
        assert s.is_valid() is False
        assert "suitable_for" in s.errors

    def test_invalid_value_raises(self):
        s = RecipeWriteSerializer(data=_minimal(suitable_for=["breakfast", "invalid_meal"]))
        assert s.is_valid() is False
        assert "suitable_for" in s.errors

    def test_all_allowed_values_pass(self):
        s = RecipeWriteSerializer(data=_minimal(
            suitable_for=["breakfast", "lunch", "dinner", "snack"]
        ))
        assert s.is_valid(), s.errors

    def test_empty_list_passes(self):
        s = RecipeWriteSerializer(data=_minimal(suitable_for=[]))
        assert s.is_valid(), s.errors


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ validate (строки 122, 127, 131) — food_group constraints                ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestValidateFoodGroup:
    def test_grain_without_grain_type_raises(self):
        s = RecipeWriteSerializer(data=_minimal(food_group="grain"))
        assert s.is_valid() is False
        assert "grain_type" in s.errors

    def test_grain_with_grain_type_passes(self):
        s = RecipeWriteSerializer(data=_minimal(
            food_group="grain", grain_type="whole"
        ))
        assert s.is_valid(), s.errors

    def test_protein_without_protein_type_raises(self):
        s = RecipeWriteSerializer(data=_minimal(food_group="protein"))
        assert s.is_valid() is False
        assert "protein_type" in s.errors

    def test_protein_with_protein_type_passes(self):
        s = RecipeWriteSerializer(data=_minimal(
            food_group="protein", protein_type="animal"
        ))
        assert s.is_valid(), s.errors

    def test_vegetable_no_constraints(self):
        s = RecipeWriteSerializer(data=_minimal(food_group="vegetable"))
        assert s.is_valid(), s.errors

    def test_no_food_group_no_constraints(self):
        s = RecipeWriteSerializer(data=_minimal())
        assert s.is_valid(), s.errors

    def test_partial_update_grain_type_from_instance(self, db):
        """MG_603: при partial_update, если food_group в attrs, grain_type берётся из instance."""
        recipe = Recipe.objects.create(
            title="Каша",
            ingredients=[{"name": "крупа"}],
            steps=[{"text": "сварить"}],
            food_group="grain",
            grain_type="whole",
        )
        # partial: меняем только title, food_group остаётся "grain", grain_type — в instance
        s = RecipeWriteSerializer(instance=recipe, data={"title": "Каша 2"}, partial=True)
        assert s.is_valid(), s.errors

    def test_partial_update_food_group_in_attrs_grain_type_in_instance(self, db):
        """attrs содержит food_group, grain_type берём из instance — должно пройти."""
        recipe = Recipe.objects.create(
            title="Каша",
            ingredients=[{"name": "крупа"}],
            steps=[{"text": "сварить"}],
            food_group="grain",
            grain_type="whole",
        )
        # Меняем food_group=grain (тот же), grain_type не передаём — должен подтянуться из instance
        s = RecipeWriteSerializer(
            instance=recipe,
            data={"title": "X", "food_group": "grain"},
            partial=True,
        )
        assert s.is_valid(), s.errors

    def test_partial_update_change_food_group_without_required_field_fails(self, db):
        """Меняем food_group на protein без protein_type — ошибка."""
        recipe = Recipe.objects.create(
            title="X",
            ingredients=[{"name": "i"}],
            steps=[{"text": "s"}],
            food_group="vegetable",
        )
        s = RecipeWriteSerializer(
            instance=recipe,
            data={"food_group": "protein"},
            partial=True,
        )
        assert s.is_valid() is False
        assert "protein_type" in s.errors
