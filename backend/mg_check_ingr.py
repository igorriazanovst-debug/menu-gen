import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.recipes.models import Recipe
# последние 3 импортированных гарнира
recipes = Recipe.objects.filter(source="parsed").order_by("-id")[:3]
for r in recipes:
    print(f"\n--- {r.title} ---")
    print(f"  ingredients ({len(r.ingredients or [])}): {r.ingredients[:2] if r.ingredients else 'EMPTY'}")
    print(f"  steps ({len(r.steps or [])}): {'есть' if r.steps else 'EMPTY'}")
