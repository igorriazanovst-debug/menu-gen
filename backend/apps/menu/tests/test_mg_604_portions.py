# MG_604_V_tests
"""
MG-604: unit-покрытие apps/menu/portions.py.

Missing lines:
  33     _age_multiplier(age < 0) → 1.0
  54-55  _member_age: исключение → None
  81-82  recipe_portion_grams: exception в блоке 1 (nutrition)
  93-94  recipe_portion_grams: exception в блоке 2 (povar_raw)
"""
import pytest

from apps.menu.portions import _age_multiplier, _member_age, daily_target_grams, recipe_portion_grams


class TestAgeMultiplier:
    def test_none_returns_adult(self):
        assert _age_multiplier(None) == 1.0

    def test_negative_age_returns_adult(self):
        # Покрывает строку 33
        assert _age_multiplier(-5) == 1.0

    @pytest.mark.parametrize(
        "age,expected",
        [
            (0, 0.40),
            (3, 0.40),
            (4, 0.55),
            (6, 0.55),
            (7, 0.70),
            (10, 0.70),
            (11, 0.85),
            (13, 0.85),
            (14, 1.00),
            (30, 1.00),
            (90, 1.00),
        ],
    )
    def test_age_ranges(self, age, expected):
        assert _age_multiplier(age) == expected


class TestMemberAge:
    def test_no_profile_returns_none(self):
        class M:
            class user:
                pass  # нет profile

        assert _member_age(M()) is None

    def test_no_birth_year_returns_none(self):
        class P:
            birth_year = None

        class M:
            class user:
                profile = P()

        assert _member_age(M()) is None

    def test_member_user_is_none_returns_none(self):
        """Покрывает строки 54-55: getattr() выбрасывает в каком-нибудь месте → except."""

        class M:
            pass  # вообще нет user

        # member.user отсутствует → getattr вернёт None, который не имеет .profile;
        # внутри try это либо None → birth_year=None → return None,
        # либо AttributeError → ловится except → return None
        assert _member_age(M()) is None

    def test_member_raises_exception_returns_none(self):
        """Явный exception в getattr через дескриптор."""

        class BoomDescriptor:
            def __get__(self, *a, **kw):
                raise RuntimeError("boom")

        class M:
            user = BoomDescriptor()

        assert _member_age(M()) is None

    def test_normal_age_calc(self):
        from datetime import date

        class P:
            birth_year = 2000

        class U:
            profile = P()

        class M:
            user = U()

        assert _member_age(M(), ref_date=date(2026, 5, 10)) == 26


class TestDailyTargetGrams:
    def test_adult(self):
        class P:
            birth_year = 1990

        class U:
            profile = P()

        class M:
            user = U()

        # 150 * 5 * 1.0 = 750
        from datetime import date

        assert daily_target_grams(M(), ref_date=date(2026, 1, 1)) == 750.0

    def test_no_birth_year(self):
        class M:
            class user:
                profile = None

        assert daily_target_grams(M()) == 750.0  # multiplier=1.0 при None


class TestRecipePortionGrams:
    def test_nutrition_weight_dict(self):
        class R:
            nutrition = {"weight": {"value": 250}}
            povar_raw = None
            servings = 1
            servings_normalized = None

        assert recipe_portion_grams(R()) == 250.0

    def test_nutrition_weight_scalar(self):
        class R:
            nutrition = {"weight": 180}
            povar_raw = None
            servings = 1
            servings_normalized = None

        assert recipe_portion_grams(R()) == 180.0

    def test_nutrition_weight_comma_decimal(self):
        class R:
            nutrition = {"weight": {"value": "180,5"}}
            povar_raw = None
            servings = 1
            servings_normalized = None

        assert recipe_portion_grams(R()) == 180.5

    def test_nutrition_exception_falls_through_to_povar(self):
        """Покрывает 81-82: exception в блоке nutrition → переход к povar_raw.

        Важно: BoomDict должен быть подклассом dict, чтобы пройти isinstance,
        иначе ветка nut.get(...) не выполняется.
        """

        class BoomDict(dict):
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            # MG_604: непустой dict, чтобы  его не подменил
            nutrition = BoomDict({"x": 1})
            povar_raw = {"dish_weight_g_calc": 400}
            servings = 2
            servings_normalized = None

        # nutrition вылетит, povar_raw даст 400/2 = 200
        assert recipe_portion_grams(R()) == 200.0

    def test_povar_raw_with_servings_normalized(self):
        class R:
            nutrition = {}
            povar_raw = {"dish_weight_g_calc": 600}
            servings = 4
            servings_normalized = 3  # приоритет над servings

        assert recipe_portion_grams(R()) == 200.0

    def test_povar_raw_exception_falls_to_default(self):
        """Покрывает 93-94: exception в блоке povar_raw → fallback 200.0."""

        class BoomPovar:
            def get(self, *a, **kw):
                raise RuntimeError("povar broken")

        class R:
            nutrition = {}
            povar_raw = BoomPovar()
            servings = 1
            servings_normalized = None

        assert recipe_portion_grams(R()) == 200.0  # DEFAULT_PORTION_G_FALLBACK

    def test_both_empty_returns_fallback(self):
        class R:
            nutrition = {}
            povar_raw = None
            servings = None
            servings_normalized = None

        assert recipe_portion_grams(R()) == 200.0

    def test_nutrition_zero_falls_through(self):
        class R:
            nutrition = {"weight": {"value": 0}}
            povar_raw = None
            servings = None
            servings_normalized = None

        assert recipe_portion_grams(R()) == 200.0
