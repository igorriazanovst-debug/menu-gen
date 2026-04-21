"""
Django management command — imports enriched recipes into PostgreSQL.

Usage:
    python manage.py populate_recipes
    python manage.py populate_recipes --input /path/to/enriched_recipes.json
    python manage.py populate_recipes --dry-run
    python manage.py populate_recipes --update   # overwrite existing by source_url
"""
import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.recipes.models import Recipe

logger = logging.getLogger(__name__)

DEFAULT_INPUT = (
    Path(__file__).resolve().parents[5] / "scripts" / "enriched_recipes.json"
)


class Command(BaseCommand):
    help = "Import nutritionist-enriched recipes from JSON into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            type=str,
            default=str(DEFAULT_INPUT),
            help="Path to enriched_recipes.json",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report without writing to DB",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing recipes matched by source_url",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        if not input_path.exists():
            raise CommandError(f"File not found: {input_path}")

        records: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))
        self.stdout.write(f"Loaded {len(records)} recipes from {input_path.name}")

        created = updated = skipped = errors = 0

        for data in records:
            try:
                result = self._import_one(data, dry_run=options["dry_run"], update=options["update"])
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                logger.warning("Error importing «%s»: %s", data.get("title", "?"), exc)

        summary = (
            f"Done  →  created: {created}  |  updated: {updated}  "
            f"|  skipped: {skipped}  |  errors: {errors}"
        )
        style = self.style.SUCCESS if errors == 0 else self.style.WARNING
        self.stdout.write(style(summary))

    # ------------------------------------------------------------------

    def _import_one(self, data: dict, dry_run: bool, update: bool) -> str:
        title = (data.get("title") or "").strip()
        if not title:
            return "skipped"

        source_url = data.get("source_url") or ""
        existing = None

        if source_url:
            existing = Recipe.objects.filter(source_url=source_url).first()
        if existing is None:
            existing = Recipe.objects.filter(title=title).first()

        if existing:
            if update and not dry_run:
                self._apply(existing, data)
                existing.save()
                return "updated"
            return "skipped"

        if not dry_run:
            Recipe.objects.create(**self._fields(data))
        return "created"

    @staticmethod
    def _fields(data: dict) -> dict:
        return {
            "title":        data["title"],
            "cook_time":    data.get("cook_time"),
            "servings":     data.get("servings"),
            "ingredients":  data.get("ingredients") or [],
            "steps":        data.get("steps") or [],
            "nutrition":    data.get("nutrition") or {},
            "categories":   data.get("categories") or [],
            "image_url":    data.get("image_url"),
            "source_url":   data.get("source_url"),
            "country":      data.get("country"),
            "is_custom":    False,
            "is_published": True,
        }

    @staticmethod
    def _apply(recipe: Recipe, data: dict) -> None:
        """Overwrite fields from data, keeping existing values when data is empty."""
        for field, value in Command._fields(data).items():
            if value not in (None, "", [], {}):
                setattr(recipe, field, value)
