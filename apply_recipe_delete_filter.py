"""
Применяет изменения бэкенда:
1. Добавляет модель DeletedRecipe в models.py
2. Создаёт и применяет миграцию
3. Обновляет RecipeViewSet.destroy() — перемещает в DeletedRecipe
4. Добавляет meal_type, calories_min, calories_max в RecipeFilter

Запускать из корня проекта:
  python apply_recipe_delete_filter.py
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).parent
BACKEND = ROOT / "backend"


def write(path: pathlib.Path, text: str):
    path.write_text(text, encoding="utf-8")
    print(f"  wrote: {path.relative_to(ROOT)}")


# ── 1. models.py ────────────────────────────────────────────────────────────

MODELS_FILE = BACKEND / "apps" / "recipes" / "models.py"
models_src = MODELS_FILE.read_text(encoding="utf-8")

DELETED_MODEL = '''

class DeletedRecipe(models.Model):
    """Рецепты, удалённые администратором. Используются для аудита и восстановления."""
    original_id   = models.IntegerField(db_index=True)
    title         = models.CharField(max_length=512)
    data          = models.JSONField()           # полный снапшот Recipe
    deleted_by    = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    deleted_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "deleted_recipes"
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"Deleted({self.original_id}, {self.title[:40]})"
'''

if "class DeletedRecipe" not in models_src:
    models_src += DELETED_MODEL
    write(MODELS_FILE, models_src)
else:
    print("  skip models.py (DeletedRecipe already exists)")


# ── 2. filters.py ───────────────────────────────────────────────────────────

FILTERS_FILE = BACKEND / "apps" / "recipes" / "filters.py"

FILTERS_NEW = '''\
from django_filters import rest_framework as filters

from .models import Recipe


class RecipeFilter(filters.FilterSet):
    category    = filters.CharFilter(method="filter_category")
    country     = filters.CharFilter(lookup_expr="icontains")
    is_custom   = filters.BooleanFilter()
    author      = filters.NumberFilter(field_name="author_id")
    meal_type   = filters.CharFilter(method="filter_meal_type")
    calories_min = filters.NumberFilter(method="filter_calories_min")
    calories_max = filters.NumberFilter(method="filter_calories_max")

    class Meta:
        model  = Recipe
        fields = ["category", "country", "is_custom", "author", "meal_type",
                  "calories_min", "calories_max"]

    def filter_category(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)

    def filter_meal_type(self, queryset, name, value):
        return queryset.filter(categories__icontains=value)

    def filter_calories_min(self, queryset, name, value):
        result = []
        for r in queryset:
            try:
                cal = float(r.nutrition.get("calories", {}).get("value", 0) or 0)
                if cal >= float(value):
                    result.append(r.pk)
            except (TypeError, ValueError):
                pass
        return queryset.filter(pk__in=result)

    def filter_calories_max(self, queryset, name, value):
        result = []
        for r in queryset:
            try:
                cal = float(r.nutrition.get("calories", {}).get("value", 0) or 0)
                if cal <= float(value):
                    result.append(r.pk)
            except (TypeError, ValueError):
                pass
        return queryset.filter(pk__in=result)
'''

write(FILTERS_FILE, FILTERS_NEW)


# ── 3. views.py — patch destroy ─────────────────────────────────────────────

VIEWS_FILE = BACKEND / "apps" / "recipes" / "views.py"
views_src = VIEWS_FILE.read_text(encoding="utf-8")

OLD_IMPORT = "from .models import Recipe, RecipeAuthor"
NEW_IMPORT  = "from .models import DeletedRecipe, Recipe, RecipeAuthor"

DESTROY_METHOD = '''
    def destroy(self, request, *args, **kwargs):
        recipe = self.get_object()
        import json
        from django.forms.models import model_to_dict
        snapshot = {
            "id":          recipe.id,
            "title":       recipe.title,
            "cook_time":   recipe.cook_time,
            "servings":    recipe.servings,
            "ingredients": recipe.ingredients,
            "steps":       recipe.steps,
            "nutrition":   recipe.nutrition,
            "categories":  recipe.categories,
            "image_url":   recipe.image_url,
            "video_url":   recipe.video_url,
            "source_url":  recipe.source_url,
            "country":     recipe.country,
            "is_custom":   recipe.is_custom,
            "is_published":recipe.is_published,
            "created_at":  str(recipe.created_at),
            "updated_at":  str(recipe.updated_at),
        }
        DeletedRecipe.objects.create(
            original_id=recipe.id,
            title=recipe.title,
            data=snapshot,
            deleted_by=request.user if request.user.is_authenticated else None,
        )
        recipe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
'''

if OLD_IMPORT in views_src:
    views_src = views_src.replace(OLD_IMPORT, NEW_IMPORT)

if "def destroy" not in views_src:
    # вставляем перед последним методом класса или в конец класса
    marker = "    @extend_schema(\n        request=Re"
    if marker in views_src:
        views_src = views_src.replace(marker, DESTROY_METHOD + "\n    @extend_schema(\n        request=Re", 1)
    else:
        # fallback — просто добавим в конец файла как отдельный кусок
        views_src += "\n" + DESTROY_METHOD

write(VIEWS_FILE, views_src)


# ── 4. makemigrations + migrate ─────────────────────────────────────────────

def docker(cmd: str):
    full = ["docker", "compose", "exec", "-T", "backend"] + cmd.split()
    print(f"  $ {' '.join(full)}")
    r = subprocess.run(full, cwd=ROOT)
    if r.returncode != 0:
        print(f"ERROR (code {r.returncode})")
        sys.exit(r.returncode)

print("\nCreating migration...")
docker("python manage.py makemigrations recipes --name deleted_recipe_and_filters")

print("\nApplying migration...")
docker("python manage.py migrate")

print("\nDone.")
