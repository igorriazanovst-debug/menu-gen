#!/usr/bin/env bash
# Fix: FieldError "Field Recipe.author cannot be both deferred and traversed
# using select_related at the same time".
#
# Filters use queryset.only("id", "ingredients") on a queryset that has
# select_related("author") from the viewset. Switch to values_list which
# bypasses the model loader entirely and is faster for the matching step.
set -eu

ROOT="/opt/menugen"
cd "$ROOT"
TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/recipes_filter_fielderror_${TS}"
mkdir -p "$BAK"
cp backend/apps/recipes/filters.py "$BAK/"
cp backend/apps/recipes/views.py   "$BAK/"
echo "backup → $BAK"

echo
echo "=== patch filters.py ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/recipes/filters.py")
s = p.read_text()

# 1) filter_calories_min — use values_list instead of .only()
s = s.replace(
    """    def filter_calories_min(self, queryset, name, value):
        ids = []
        for r in queryset.only("id", "nutrition"):
            try:
                cal = float((r.nutrition or {}).get("calories", {}).get("value", 0) or 0)
                if cal >= float(value):
                    ids.append(r.pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)""",
    """    def filter_calories_min(self, queryset, name, value):
        ids = []
        for pk, nut in queryset.values_list("id", "nutrition"):
            try:
                cal = float((nut or {}).get("calories", {}).get("value", 0) or 0)
                if cal >= float(value):
                    ids.append(pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)""",
)

# 2) filter_calories_max — same
s = s.replace(
    """    def filter_calories_max(self, queryset, name, value):
        ids = []
        for r in queryset.only("id", "nutrition"):
            try:
                cal = float((r.nutrition or {}).get("calories", {}).get("value", 0) or 0)
                if cal <= float(value):
                    ids.append(r.pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)""",
    """    def filter_calories_max(self, queryset, name, value):
        ids = []
        for pk, nut in queryset.values_list("id", "nutrition"):
            try:
                cal = float((nut or {}).get("calories", {}).get("value", 0) or 0)
                if cal <= float(value):
                    ids.append(pk)
            except (TypeError, ValueError, AttributeError):
                pass
        return queryset.filter(pk__in=ids)""",
)

# 3) ingredients_all — use values_list and inline matching (no Recipe-method calls).
s = s.replace(
    """    def filter_ingredients_all(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = [r.pk for r in queryset.only("id", "ingredients") if _recipe_matches_all(r, needles)]
        return queryset.filter(pk__in=ids)""",
    """    def filter_ingredients_all(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = []
        for pk, ingredients in queryset.values_list("id", "ingredients"):
            names = _names_from_raw(ingredients)
            if all(any(n in name for name in names) for n in needles):
                ids.append(pk)
        return queryset.filter(pk__in=ids)""",
)

# 4) ingredients_any
s = s.replace(
    """    def filter_ingredients_any(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = [r.pk for r in queryset.only("id", "ingredients") if _recipe_matches_any(r, needles)]
        return queryset.filter(pk__in=ids)""",
    """    def filter_ingredients_any(self, queryset, name, value):
        needles = self._parse_csv(value)
        if not needles:
            return queryset
        ids = []
        for pk, ingredients in queryset.values_list("id", "ingredients"):
            names = _names_from_raw(ingredients)
            if any(any(n in name for name in names) for n in needles):
                ids.append(pk)
        return queryset.filter(pk__in=ids)""",
)

# 5) exclude_allergens — use values_list
s = s.replace(
    """        good_ids = []
        for r in queryset.only("id", "ingredients"):
            if not _recipe_matches_any(r, allergens):
                good_ids.append(r.pk)
        return queryset.filter(pk__in=good_ids)""",
    """        good_ids = []
        for pk, ingredients in queryset.values_list("id", "ingredients"):
            names = _names_from_raw(ingredients)
            if not any(any(a in name for name in names) for a in allergens):
                good_ids.append(pk)
        return queryset.filter(pk__in=good_ids)""",
)

# 6) Add the new top-level helper _names_from_raw and keep old _ingredient_names
#    for compatibility with _recipe_fridge_score (used in views.py).
old_helper_block = """def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _ingredient_names(recipe: Recipe) -> list[str]:
    out = []
    for ing in recipe.ingredients or []:
        if isinstance(ing, dict):
            name = ing.get("name")
            if name:
                out.append(_normalize(str(name)))
    return out


def _recipe_matches_any(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    return any(any(n in name for name in names) for n in needles)


def _recipe_matches_all(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    for n in needles:
        if not any(n in name for name in names):
            return False
    return True


def _recipe_fridge_score(recipe: Recipe, needles: list[str]) -> int:
    names = _ingredient_names(recipe)
    score = 0
    for n in needles:
        if any(n in name for name in names):
            score += 1
    return score"""

new_helper_block = """def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _names_from_raw(ingredients) -> list[str]:
    \"\"\"Lower-cased ingredient names from a raw JSON list (no model instance).\"\"\"
    out = []
    for ing in ingredients or []:
        if isinstance(ing, dict):
            n = ing.get("name")
            if n:
                out.append(_normalize(str(n)))
    return out


def _ingredient_names(recipe: Recipe) -> list[str]:
    return _names_from_raw(recipe.ingredients)


def _recipe_matches_any(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    return any(any(n in name for name in names) for n in needles)


def _recipe_matches_all(recipe: Recipe, needles: list[str]) -> bool:
    names = _ingredient_names(recipe)
    for n in needles:
        if not any(n in name for name in names):
            return False
    return True


def _recipe_fridge_score(recipe: Recipe, needles: list[str]) -> int:
    names = _ingredient_names(recipe)
    score = 0
    for n in needles:
        if any(n in name for name in names):
            score += 1
    return score"""

assert old_helper_block in s, "marker not found for helper block"
s = s.replace(old_helper_block, new_helper_block)

p.write_text(s)
print("filters.py patched.")
PYEOF

echo
echo "=== patch views.py: fridge scoring also uses values_list ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/recipes/views.py")
s = p.read_text()

old = """        if fridge_needles:
            # Compute scores across queryset; pick top-N by score.
            scored = []
            for r in queryset.only("id", "ingredients"):
                s = _recipe_fridge_score(r, fridge_needles)
                scored.append((r.pk, s))"""

new = """        if fridge_needles:
            # Compute scores across queryset; pick top-N by score.
            from .filters import _names_from_raw

            scored = []
            for pk, ingredients in queryset.values_list("id", "ingredients"):
                names = _names_from_raw(ingredients)
                score = sum(1 for n in fridge_needles if any(n in name for name in names))
                scored.append((pk, score))"""

assert old in s, "marker not found in views.py fridge block"
s = s.replace(old, new)

# fix variable shadow (s = _recipe_fridge_score ... scored.sort(...) uses `s` too)
s = s.replace(
    "scored.sort(key=lambda x: (-x[1], -x[0]))",
    "scored.sort(key=lambda x: (-x[1], -x[0]))",  # noop, ensure exists
)

p.write_text(s)
print("views.py patched.")
PYEOF

echo
echo "=== black + isort + flake8 ==="
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
$COMPOSE exec -T backend bash -lc '
  black --exclude="/(migrations|scripts)/" apps/recipes/filters.py apps/recipes/views.py
  isort apps/recipes/filters.py apps/recipes/views.py
  flake8 apps/recipes/filters.py apps/recipes/views.py
'

echo
echo "=== run tests ==="
$COMPOSE exec -T backend pytest -q apps/recipes/ --tb=line --no-header 2>&1 | tail -20

echo
echo "=== smoke: hit the endpoint that failed ==="
$COMPOSE exec -T backend python manage.py shell -c "
from django.test import RequestFactory
from apps.recipes.views import RecipeViewSet
from apps.recipes.models import Recipe
import urllib.parse as up

# emulate: GET /api/v1/recipes/?ingredients_all=говядина
rf = RequestFactory()
req = rf.get('/api/v1/recipes/?page=1&ingredients_all=' + up.quote('говядина'))

from rest_framework.request import Request
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import AnonymousUser
req.user = AnonymousUser()

view = RecipeViewSet()
view.action = 'list'
view.request = Request(req)
view.kwargs = {}
view.format_kwarg = None

qs = view.filter_queryset(view.get_queryset())
print('Matched recipes:', qs.count())
for r in qs[:3]:
    print('  ', r.id, '-', r.title[:60])
"

echo
echo "DONE."
echo "Now: git add -A && git commit -m 'fix(recipes): FieldError on ingredients filters' && git push"
