# MG_604_V_tests
"""
MG-604: unit-покрытие apps/menu/exceptions.py.

Missing lines:
  42  MenuGeneratorError.to_response (базовый)
  77  EmptyRolePoolError: reason_hint включён в сообщение
"""
import pytest

from apps.menu.exceptions import EmptyRolePoolError, MenuGeneratorError


class TestMenuGeneratorError:
    def test_to_response_basic(self):
        err = MenuGeneratorError("Что-то пошло не так")
        resp = err.to_response()
        assert resp == {"error": "menu_generator_error", "message": "Что-то пошло не так"}

    def test_default_code_attribute(self):
        assert MenuGeneratorError.code == "menu_generator_error"


class TestEmptyRolePoolError:
    def test_basic_message(self):
        err = EmptyRolePoolError(role="protein", meal_slot="lunch", day_offset=0)
        assert err.role == "protein"
        assert err.meal_slot == "lunch"
        assert err.day_offset == 0
        assert err.member_name == ""
        assert "обеда" in str(err)
        assert "белковый компонент" in str(err)
        assert "(день 1)" in str(err)

    def test_with_member_name(self):
        err = EmptyRolePoolError(
            role="vegetable", meal_slot="dinner", day_offset=2, member_name="Маша"
        )
        assert " для Маша" in str(err)
        assert "(день 3)" in str(err)

    def test_with_reason_hint(self):
        # Покрывает строку 77: if reason_hint
        err = EmptyRolePoolError(
            role="grain", meal_slot="breakfast", day_offset=0,
            reason_hint="Все рецепты вызывают аллергию.",
        )
        assert "Все рецепты вызывают аллергию." in str(err)

    def test_unknown_role_falls_back_to_raw(self):
        err = EmptyRolePoolError(role="exotic", meal_slot="lunch", day_offset=0)
        # неизвестная роль остаётся как есть
        assert "exotic" in str(err)

    def test_unknown_meal_slot_falls_back_to_raw(self):
        err = EmptyRolePoolError(role="protein", meal_slot="brunch", day_offset=0)
        assert "brunch" in str(err)

    def test_to_response_with_details(self):
        err = EmptyRolePoolError(
            role="protein", meal_slot="lunch", day_offset=1, member_name="Папа",
        )
        resp = err.to_response()
        assert resp["error"] == "empty_role_pool"
        assert resp["details"]["role"] == "protein"
        assert resp["details"]["meal_slot"] == "lunch"
        assert resp["details"]["day_offset"] == 1
        assert resp["details"]["member_name"] == "Папа"

    def test_code_is_empty_role_pool(self):
        assert EmptyRolePoolError.code == "empty_role_pool"
