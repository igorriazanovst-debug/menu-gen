from django.apps import AppConfig


class RecipesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recipes"

    def ready(self):
        from . import signals  # noqa: F401  (MG_RECIPELINK)
