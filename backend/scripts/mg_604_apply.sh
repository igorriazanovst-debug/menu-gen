#!/usr/bin/env bash
# MG-604 apply: покрытие остатков
#  - apps/recipes/permissions.py  77% → 100%
#  - apps/recipes/views.py        91% → 100%
#  - apps/menu/exceptions.py      93% → 100%
#  - apps/menu/portions.py        88% → 100%
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
BACKEND="$ROOT/backend"
TS=$(date +%Y%m%d_%H%M%S)

RECIPES_CONFTEST="$BACKEND/apps/recipes/tests/conftest.py"
TEST_PERMS="$BACKEND/apps/recipes/tests/test_mg_604_permissions.py"
TEST_VIEWS="$BACKEND/apps/recipes/tests/test_mg_604_views_country_apply.py"
TEST_EXC="$BACKEND/apps/menu/tests/test_mg_604_exceptions.py"
TEST_PORT="$BACKEND/apps/menu/tests/test_mg_604_portions.py"

echo "=========================================="
echo "  MG-604 APPLY  ($TS)"
echo "=========================================="

# ── 1. conftest.py для apps/recipes/tests ────────────────────────────────
cat > "$RECIPES_CONFTEST" <<'PYEOF'
# MG_604_V_tests: общие фикстуры для apps/recipes/tests
import pytest
from rest_framework.test import APIClient

from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def plain_user(db):
    return User.objects.create_user(
        email="plain@example.com", name="Обычный", password="x12345",
        user_type="user",
    )


@pytest.fixture
def author(db):
    return User.objects.create_user(
        email="author@example.com", name="Автор", password="x12345",
        user_type="recipe_author",
    )


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com", name="Админ", password="x12345",
        user_type="admin",
    )


@pytest.fixture
def recipe(db, author):
    return Recipe.objects.create(
        title="Базовый рецепт",
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "шаг 1"}],
        nutrition={"calories": {"value": "300"}},
        categories=["Завтраки"],
        author=author,
        is_published=True,
    )
PYEOF
echo "Создан: $RECIPES_CONFTEST"

# ── 2. test_mg_604_permissions.py ────────────────────────────────────────
cat > "$TEST_PERMS" <<'PYEOF'
# MG_604_V_tests
"""
MG-604: unit-покрытие apps/recipes/permissions.py.

Missing lines:
  9   IsAuthorOrAdmin: SAFE_METHODS → True
  11  IsAuthorOrAdmin: user_type == 'admin' → True
  20  IsRecipeAuthorRole: SAFE_METHODS → True
"""
import pytest

from apps.recipes.permissions import IsAuthorOrAdmin, IsRecipeAuthorRole


class _Req:
    def __init__(self, method, user):
        self.method = method
        self.user = user


class _Obj:
    def __init__(self, author):
        self.author = author


@pytest.mark.django_db
class TestIsAuthorOrAdmin:
    def test_safe_method_returns_true(self, plain_user, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("GET", plain_user)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_admin_can_edit(self, admin, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", admin)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_author_can_edit(self, author, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", author)
        assert perm.has_object_permission(req, None, recipe) is True

    def test_other_user_cannot_edit(self, plain_user, recipe):
        perm = IsAuthorOrAdmin()
        req = _Req("PATCH", plain_user)
        assert perm.has_object_permission(req, None, recipe) is False


@pytest.mark.django_db
class TestIsRecipeAuthorRole:
    def test_safe_method_returns_true(self, plain_user):
        perm = IsRecipeAuthorRole()
        req = _Req("GET", plain_user)
        assert perm.has_permission(req, None) is True

    def test_recipe_author_can(self, author):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", author)
        assert perm.has_permission(req, None) is True

    def test_admin_can(self, admin):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", admin)
        assert perm.has_permission(req, None) is True

    def test_plain_user_cannot(self, plain_user):
        perm = IsRecipeAuthorRole()
        req = _Req("POST", plain_user)
        assert perm.has_permission(req, None) is False
PYEOF
echo "Создан: $TEST_PERMS"

# ── 3. test_mg_604_views_country_apply.py ───────────────────────────────
cat > "$TEST_VIEWS" <<'PYEOF'
# MG_604_V_tests
"""
MG-604: покрытие двух views в apps/recipes/views.py.

Missing lines:
  24-33   RecipeCountryListView.get (целиком)
  141-145 RecipeAuthorApplyView.perform_create (duplicate check + save)
"""
import pytest
from django.urls import reverse

from apps.recipes.models import Recipe, RecipeAuthor


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ RecipeCountryListView                                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestRecipeCountryList:
    def test_empty_returns_empty_list(self, client):
        resp = client.get(reverse("recipe-countries"))
        assert resp.status_code == 200
        assert resp.data == []

    def test_returns_distinct_sorted_countries(self, client, db, author):
        for c in ["Россия", "Италия", "Россия", "Грузия"]:
            Recipe.objects.create(
                title=f"Рец {c}",
                ingredients=[{"name": "и"}],
                steps=[{"text": "ш"}],
                country=c,
                is_published=True,
                author=author,
            )
        resp = client.get(reverse("recipe-countries"))
        assert resp.status_code == 200
        # отсортированы, без дубликатов
        assert resp.data == sorted({"Россия", "Италия", "Грузия"})

    def test_excludes_unpublished(self, client, db, author):
        Recipe.objects.create(
            title="Скрытый", ingredients=[{"name": "и"}], steps=[{"text": "ш"}],
            country="Япония", is_published=False, author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert "Япония" not in resp.data

    def test_excludes_empty_country(self, client, db, author):
        Recipe.objects.create(
            title="Без страны", ingredients=[{"name": "и"}], steps=[{"text": "ш"}],
            country="", is_published=True, author=author,
        )
        Recipe.objects.create(
            title="Только пробелы", ingredients=[{"name": "и"}], steps=[{"text": "ш"}],
            country="   ", is_published=True, author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert resp.data == []  # обе записи отфильтрованы

    def test_strips_whitespace(self, client, db, author):
        Recipe.objects.create(
            title="С пробелами", ingredients=[{"name": "и"}], steps=[{"text": "ш"}],
            country="  Франция  ", is_published=True, author=author,
        )
        resp = client.get(reverse("recipe-countries"))
        assert "Франция" in resp.data


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║ RecipeAuthorApplyView                                                   ║
# ╚═════════════════════════════════════════════════════════════════════════╝
@pytest.mark.django_db
class TestRecipeAuthorApply:
    def test_apply_success(self, client, plain_user):
        client.force_authenticate(plain_user)
        resp = client.post(
            reverse("recipe-author-apply"),
            {"motivation_text": "Хочу делиться рецептами"},
            format="json",
        )
        assert resp.status_code == 201
        assert RecipeAuthor.objects.filter(user=plain_user).exists()

    def test_apply_duplicate_raises_400(self, client, plain_user):
        RecipeAuthor.objects.create(user=plain_user, motivation_text="первая заявка")
        client.force_authenticate(plain_user)
        resp = client.post(
            reverse("recipe-author-apply"),
            {"motivation_text": "вторая попытка"},
            format="json",
        )
        assert resp.status_code == 400

    def test_apply_unauthenticated(self, client):
        resp = client.post(reverse("recipe-author-apply"), {}, format="json")
        assert resp.status_code == 401
PYEOF
echo "Создан: $TEST_VIEWS"

# ── 4. test_mg_604_exceptions.py ─────────────────────────────────────────
cat > "$TEST_EXC" <<'PYEOF'
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
PYEOF
echo "Создан: $TEST_EXC"

# ── 5. test_mg_604_portions.py ───────────────────────────────────────────
cat > "$TEST_PORT" <<'PYEOF'
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

from apps.menu.portions import (
    _age_multiplier,
    _member_age,
    daily_target_grams,
    recipe_portion_grams,
)


class TestAgeMultiplier:
    def test_none_returns_adult(self):
        assert _age_multiplier(None) == 1.0

    def test_negative_age_returns_adult(self):
        # Покрывает строку 33
        assert _age_multiplier(-5) == 1.0

    @pytest.mark.parametrize("age,expected", [
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
    ])
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
        """Покрывает 81-82: exception в блоке nutrition → переход к povar_raw."""
        class BoomDict:
            def get(self, *a, **kw):
                raise RuntimeError("nutrition broken")

        class R:
            nutrition = BoomDict()
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
PYEOF
echo "Создан: $TEST_PORT"

# ── 6. AST-проверка всех файлов ──────────────────────────────────────────
echo
echo "--- AST checks ---"
for f in "$RECIPES_CONFTEST" "$TEST_PERMS" "$TEST_VIEWS" "$TEST_EXC" "$TEST_PORT"; do
  rel="${f#$BACKEND/}"
  $COMPOSE exec -T backend python -c "import ast; ast.parse(open('$rel').read()); print('$rel: OK')"
done

# ── 7. Прогон новых тестов ───────────────────────────────────────────────
echo
echo "--- pytest test_mg_604_* ---"
$COMPOSE exec -T backend pytest \
  apps/recipes/tests/test_mg_604_permissions.py \
  apps/recipes/tests/test_mg_604_views_country_apply.py \
  apps/menu/tests/test_mg_604_exceptions.py \
  apps/menu/tests/test_mg_604_portions.py \
  -v --tb=short 2>&1 | tail -80

# ── 8. Полный прогон + coverage ──────────────────────────────────────────
echo
echo "--- coverage report (apps/menu + apps/recipes) ---"
$COMPOSE exec -T backend bash -lc '
  cd /app
  coverage erase
  coverage run --rcfile=.coveragerc -m pytest apps/menu/ apps/recipes/ -q --tb=no 2>&1 | tail -5
  echo
  coverage report --rcfile=.coveragerc --show-missing
'

echo
echo "=========================================="
echo "  MG-604 APPLY DONE"
echo "=========================================="
