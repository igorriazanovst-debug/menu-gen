#!/usr/bin/env bash
# Diagnostic script for recipes filters + detail card task
# Run from /opt/menugen on the dev host
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/recipes_diag_${TS}.txt"

exec > >(tee "$OUT") 2>&1

echo "=========================================="
echo "  RECIPES FILTERS + DETAIL DIAG  ($TS)"
echo "=========================================="

cd "$ROOT"

echo
echo "--- [1] Git state ---"
git log --oneline -5
git status --short

echo
echo "--- [2] Mobile: recipes feature tree ---"
ls -la mobile/menugen_app/lib/features/recipes/
find mobile/menugen_app/lib/features/recipes -type f -name "*.dart"

echo
echo "--- [3] Mobile: current recipes_screen.dart (FULL) ---"
cat -n mobile/menugen_app/lib/features/recipes/screens/recipes_screen.dart

echo
echo "--- [4] Mobile: current recipe_detail_screen.dart (FULL) ---"
cat -n mobile/menugen_app/lib/features/recipes/screens/recipe_detail_screen.dart

echo
echo "--- [5] Mobile: recipes_bloc.dart (FULL) ---"
cat -n mobile/menugen_app/lib/features/recipes/bloc/recipes_bloc.dart

echo
echo "--- [6] Mobile: ApiClient + ApiException ---"
ls -la mobile/menugen_app/lib/core/api/
cat -n mobile/menugen_app/lib/core/api/api_client.dart 2>/dev/null | head -120
echo "--- api_exception.dart ---"
cat -n mobile/menugen_app/lib/core/api/api_exception.dart 2>/dev/null | head -60

echo
echo "--- [7] Mobile: app_router.dart (FULL) ---"
cat -n mobile/menugen_app/lib/core/router/app_router.dart

echo
echo "--- [8] Mobile: main.dart bloc providers ---"
grep -nE "BlocProvider|RecipesBloc|FridgeBloc" mobile/menugen_app/lib/main.dart 2>/dev/null || echo "(no main.dart matches)"
cat -n mobile/menugen_app/lib/main.dart 2>/dev/null | head -80

echo
echo "--- [9] Mobile: pubspec.yaml dependencies ---"
grep -E "^\s+(flutter_bloc|equatable|cached_network_image|dio|go_router|drift):" mobile/menugen_app/pubspec.yaml

echo
echo "--- [10] Backend: recipes app structure ---"
ls -la backend/apps/recipes/
echo
echo "--- views.py FULL ---"
$COMPOSE exec -T backend cat -n apps/recipes/views.py

echo
echo "--- [11] Backend: filters.py FULL ---"
$COMPOSE exec -T backend cat -n apps/recipes/filters.py

echo
echo "--- [12] Backend: urls.py FULL ---"
$COMPOSE exec -T backend cat -n apps/recipes/urls.py

echo
echo "--- [13] Backend: serializers.py FULL ---"
$COMPOSE exec -T backend cat -n apps/recipes/serializers.py

echo
echo "--- [14] Backend: models.py FULL ---"
$COMPOSE exec -T backend cat -n apps/recipes/models.py

echo
echo "--- [15] Backend: existing migrations in recipes ---"
$COMPOSE exec -T backend ls -la apps/recipes/migrations/

echo
echo "--- [16] Backend: existing categories sample (top 30 unique) ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from collections import Counter
c = Counter()
for r in Recipe.objects.filter(is_published=True).only('categories')[:1000]:
    if isinstance(r.categories, list):
        for cat in r.categories:
            c[str(cat).strip()] += 1
for cat, n in c.most_common(30):
    print(f'{n:5d}  {cat}')
"

echo
echo "--- [17] Backend: existing food_group distribution ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from django.db.models import Count
for row in Recipe.objects.filter(is_published=True).values('food_group').annotate(n=Count('id')).order_by('-n'):
    print(f\"{row['n']:5d}  {row['food_group'] or '(null)'}\")
"

echo
echo "--- [18] Backend: existing protein_type distribution ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from django.db.models import Count
for row in Recipe.objects.filter(is_published=True).values('protein_type').annotate(n=Count('id')).order_by('-n'):
    print(f\"{row['n']:5d}  {row['protein_type'] or '(null)'}\")
"

echo
echo "--- [19] Backend: countries available ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from django.db.models import Count
for row in Recipe.objects.filter(is_published=True).values('country').annotate(n=Count('id')).order_by('-n')[:30]:
    print(f\"{row['n']:5d}  {row['country'] or '(null)'}\")
"

echo
echo "--- [20] Backend: suitable_for distribution (meal types) ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
from collections import Counter
c = Counter()
total = 0
for r in Recipe.objects.filter(is_published=True).only('suitable_for'):
    total += 1
    if isinstance(r.suitable_for, list):
        for s in r.suitable_for:
            c[str(s)] += 1
print(f'total recipes: {total}')
for k, n in c.most_common():
    print(f'{n:5d}  {k}')
"

echo
echo "--- [21] Backend: sample ingredient names (random 30 from 5 recipes) ---"
$COMPOSE exec -T backend python manage.py shell -c "
from apps.recipes.models import Recipe
import random
qs = list(Recipe.objects.filter(is_published=True).only('id','title','ingredients')[:50])
random.shuffle(qs)
for r in qs[:5]:
    print(f'--- {r.id}: {r.title}')
    for ing in (r.ingredients or [])[:6]:
        print(f'    {ing}')
"

echo
echo "--- [22] Backend: User model fields (allergies / disliked_products) ---"
$COMPOSE exec -T backend grep -nE "allergies|disliked_products|^class User" apps/users/models.py | head -20

echo
echo "--- [23] Backend: existing Favorite model search (anywhere) ---"
$COMPOSE exec -T backend bash -lc '
  grep -rni "favorite" apps/ --include="*.py" | head -30 || echo "(no matches)"
'

echo
echo "--- [24] Backend: existing /recipes URL test ---"
$COMPOSE exec -T backend python manage.py show_urls 2>/dev/null | grep -i "recipe\|favorite" | head -30 || \
  $COMPOSE exec -T backend python manage.py shell -c "
from django.urls import get_resolver
def walk(urlpatterns, prefix=''):
    for p in urlpatterns:
        if hasattr(p, 'url_patterns'):
            walk(p.url_patterns, prefix + str(p.pattern))
        else:
            full = prefix + str(p.pattern)
            if 'recip' in full.lower() or 'favorit' in full.lower():
                print(full)
walk(get_resolver().url_patterns)
"

echo
echo "--- [25] Backend: fridge endpoint shape (we'll need to read fridge items) ---"
$COMPOSE exec -T backend cat -n apps/fridge/views.py | head -80

echo
echo "--- [26] Backend: products app (do we have a Product reference table?) ---"
ls -la backend/apps/fridge/ 2>/dev/null
$COMPOSE exec -T backend grep -nE "^class " apps/fridge/models.py

echo
echo "--- [27] CI status ---"
gh run list --repo igorriazanovst-debug/menu-gen --branch main --limit 5 2>/dev/null || echo "(gh not available or not authed)"

echo
echo "=========================================="
echo "  DIAG DONE → $OUT"
echo "=========================================="
