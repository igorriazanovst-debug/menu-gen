# MG_RECIPELINK — rebuild product links when a recipe is saved.
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Recipe


@receiver(post_save, sender=Recipe)
def _mg_recipelink_on_recipe_save(sender, instance, **kwargs):
    if getattr(instance, "_mg_skip_link_rebuild", False):
        return
    try:
        from .recipe_products import rebuild_recipe_links

        rebuild_recipe_links(instance, force=True)
    except Exception:
        # Never block recipe save on link/AI failure.
        pass
