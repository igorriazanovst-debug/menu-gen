from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .forms import RecipeAdminForm
from .models import Recipe, RecipeAuthor, RecipeFavorite

# Human help texts (meaning in DB + allowed values), translatable.
HELP = {
    "title": _("Recipe name. Stored as-is (free text)."),
    "legacy_id": _("Original ID from the import source. Read-only."),
    "cook_time": _("Cooking time as free text, e.g. '30 min'. Prefer cook_time_min for numbers."),
    "cook_time_min": _("Cooking time in minutes (integer)."),
    "servings": _("Number of servings as given by the source."),
    "servings_normalized": _("Normalized servings count used by the generator."),
    "portion_g": _("Weight of one serving, grams."),
    "ingredients": _(
        "List of ingredients. Each row: name, quantity, unit, grams. " "Grams are used to compute nutrition."
    ),
    "steps": _("Ordered cooking steps. Numbering is assigned automatically."),
    "nutrition": _("Per-100g nutrition object: calories, proteins, fats, carbs, sugars."),
    "categories": _(
        "Free tags. Allowed values mirror dish types: "
        "soup, main, salad, side, dessert, drink, bakery, sauce, snack, breakfast_dish."
    ),
    "allergens": _(
        "Allergens present in the dish. Allowed: eggs, milk, gluten, fish, " "shellfish, nuts, peanuts, soy, sesame."
    ),
    "suitable_for": _("Meal slots this dish fits. Allowed: breakfast, lunch, dinner, snack."),
    "dish_type": _("Dish type (first course / main / dessert ...). One value."),
    "food_group": _("Primary food group: grain, protein, vegetable, fruit, dairy, oil, other."),
    "protein_type": _("Protein origin: animal, plant, mixed."),
    "grain_type": _("Grain type: whole, refined."),
    "cooking_method": _("Cooking method: boiled, baked, fried, grilled, raw, stewed, steamed."),
    "source": _("Recipe origin: own, import, user, parsed."),
    "country": _("Country / cuisine as free text."),
    "oil_tsp": _("Oil consumption in teaspoons."),
    "serving_size_label": _("Serving size caption, e.g. '1 plate / 200 g'."),
    "has_added_sugar": _("Contains added sugar."),
    "is_fatty_fish": _("Dish is fatty fish."),
    "is_red_meat": _("Dish is red meat."),
    "is_vegan": _("Vegan."),
    "is_vegetarian": _("Vegetarian."),
    "is_gluten_free": _("Gluten-free."),
    "is_lactose_free": _("Lactose-free."),
    "is_custom": _("Created by a user (not from base import)."),
    "is_published": _("Visible to clients."),
    "image_url": _("Cover image URL."),
    "video_url": _("Video URL."),
    "source_url": _("Original source URL."),
    "kcal": _("Calories per serving."),
    "proteins": _("Proteins per serving, g."),
    "fats": _("Fats per serving, g."),
    "carbs": _("Carbs per serving, g."),
    "kcal_per_100g": _("Calories per 100 g."),
    "proteins_per_100g": _("Proteins per 100 g."),
    "fats_per_100g": _("Fats per 100 g."),
    "carbs_per_100g": _("Carbs per 100 g."),
    "sugars_per_100g": _("Sugars per 100 g."),
}

# Human field labels, translatable (verbose names for the form).
LABELS = {
    "title": _("Title"),
    "legacy_id": _("Legacy ID"),
    "cook_time": _("Cook time (text)"),
    "cook_time_min": _("Cook time (min)"),
    "servings": _("Servings"),
    "servings_normalized": _("Servings (normalized)"),
    "portion_g": _("Portion, g"),
    "nutrition": _("Nutrition (per 100 g)"),
    "dish_type": _("Dish type"),
    "food_group": _("Food group"),
    "protein_type": _("Protein type"),
    "grain_type": _("Grain type"),
    "cooking_method": _("Cooking method"),
    "source": _("Source"),
    "country": _("Country / cuisine"),
    "oil_tsp": _("Oil, tsp"),
    "serving_size_label": _("Serving size label"),
    "has_added_sugar": _("Has added sugar"),
    "is_fatty_fish": _("Fatty fish"),
    "is_red_meat": _("Red meat"),
    "is_vegan": _("Vegan"),
    "is_vegetarian": _("Vegetarian"),
    "is_gluten_free": _("Gluten-free"),
    "is_lactose_free": _("Lactose-free"),
    "is_custom": _("Custom"),
    "is_published": _("Published"),
    "image_url": _("Image URL"),
    "video_url": _("Video URL"),
    "source_url": _("Source URL"),
    "kcal": _("Calories / serving"),
    "proteins": _("Proteins / serving"),
    "fats": _("Fats / serving"),
    "carbs": _("Carbs / serving"),
    "kcal_per_100g": _("Calories / 100 g"),
    "proteins_per_100g": _("Proteins / 100 g"),
    "fats_per_100g": _("Fats / 100 g"),
    "carbs_per_100g": _("Carbs / 100 g"),
    "sugars_per_100g": _("Sugars / 100 g"),
}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    form = RecipeAdminForm

    list_display = (
        "id",
        "title",
        "dish_type",
        "country",
        "source",
        "is_custom",
        "is_published",
        "author",
        "created_at",
    )
    list_filter = (
        "dish_type",
        "source",
        "food_group",
        "is_custom",
        "is_published",
        "is_vegan",
        "is_vegetarian",
        "country",
    )
    search_fields = ("title", "legacy_id")
    raw_id_fields = ("author",)
    readonly_fields = ("legacy_id", "created_at", "updated_at")
    actions = ["publish", "unpublish"]
    save_on_top = True

    fieldsets = (
        (
            _("Main"),
            {
                "fields": (
                    "title",
                    "country",
                    "source",
                    "is_custom",
                    "is_published",
                    "author",
                    "image_url",
                    "video_url",
                    "source_url",
                ),
            },
        ),
        (
            _("Content"),
            {
                "fields": ("ingredients", "steps"),
            },
        ),
        (
            _("Classification"),
            {
                "fields": (
                    "dish_type",
                    "categories",
                    "suitable_for",
                    "food_group",
                    "protein_type",
                    "grain_type",
                    "cooking_method",
                ),
            },
        ),
        (
            _("Flags"),
            {
                "fields": (
                    "is_vegan",
                    "is_vegetarian",
                    "is_gluten_free",
                    "is_lactose_free",
                    "is_fatty_fish",
                    "is_red_meat",
                    "has_added_sugar",
                    "allergens",
                ),
            },
        ),
        (
            _("Portion & timing"),
            {
                "fields": (
                    "servings",
                    "servings_normalized",
                    "portion_g",
                    "serving_size_label",
                    "cook_time",
                    "cook_time_min",
                    "oil_tsp",
                ),
            },
        ),
        (
            _("Nutrition"),
            {
                "fields": (
                    "nutrition",
                    "kcal",
                    "proteins",
                    "fats",
                    "carbs",
                    "kcal_per_100g",
                    "proteins_per_100g",
                    "fats_per_100g",
                    "carbs_per_100g",
                    "sugars_per_100g",
                ),
            },
        ),
        (
            _("Service"),
            {
                "fields": ("legacy_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, field in form.base_fields.items():
            if name in LABELS:
                field.label = LABELS[name]
            if name in HELP:
                field.help_text = HELP[name]
        return form

    @admin.action(description=_("Publish selected"))
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description=_("Unpublish selected"))
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "applied_at", "approved_at")
    list_filter = ("status",)
    raw_id_fields = ("user",)
    actions = ["approve", "reject"]

    @admin.action(description="Одобрить заявки")
    def approve(self, request, queryset):
        from django.utils import timezone

        from apps.users.models import User

        now = timezone.now()
        for obj in queryset:
            obj.status = "approved"
            obj.approved_at = now
            obj.save(update_fields=["status", "approved_at"])
            User.objects.filter(id=obj.user_id).update(user_type="recipe_author")

    @admin.action(description="Отклонить заявки")
    def reject(self, request, queryset):
        queryset.update(status="rejected")


@admin.register(RecipeFavorite)
class RecipeFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "recipe", "is_favorite", "created_at")
    list_filter = ("is_favorite",)
    raw_id_fields = ("user", "recipe")
    search_fields = ("recipe__title", "user__email", "user__name")
