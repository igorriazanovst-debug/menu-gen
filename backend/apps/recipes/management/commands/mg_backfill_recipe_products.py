from django.core.management.base import BaseCommand

from apps.recipes.recipe_products import backfill


class Command(BaseCommand):
    help = "MG_RECIPELINK: backfill RecipeProduct links (canonicalize + match + categorize)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--menu", type=int, default=None)
        parser.add_argument("--recipe", type=int, nargs="*", default=None)
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **opts):
        stats = backfill(
            force=opts["force"],
            menu_id=opts.get("menu"),
            recipe_ids=opts.get("recipe"),
            limit=opts.get("limit"),
            log=lambda m: self.stdout.write(str(m)),
        )
        self.stdout.write(self.style.SUCCESS(str(stats)))
