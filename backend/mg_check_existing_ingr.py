import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.recipes.models import Recipe
# рецепт с ингредиентами из старой базы
r = Recipe.objects.filter(source__in=["own","import"]).exclude(ingredients=[]).first()
if r:
    print(f"--- {r.title} ---")
    print(f"ingredients[0:3]: {r.ingredients[:3]}")
