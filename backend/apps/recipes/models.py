from django.db import models
from django.contrib.postgres.indexes import GinIndex

from apps.users.models import User


class Recipe(models.Model):
    legacy_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    cook_time = models.CharField(max_length=64, null=True, blank=True)
    servings = models.PositiveSmallIntegerField(null=True, blank=True)
    servings_normalized = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Нормализованное число порций (MG-104d-5)")
    ingredients = models.JSONField(default=list)
    steps = models.JSONField(default=list)
    nutrition = models.JSONField(default=dict)
    categories = models.JSONField(default=list)
    image_url = models.URLField(null=True, blank=True, max_length=1024)
    video_url = models.URLField(null=True, blank=True, max_length=1024)
    source_url = models.URLField(null=True, blank=True, max_length=1024)
    country = models.CharField(max_length=100, null=True, blank=True)
    is_custom = models.BooleanField(default=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="recipes")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class FoodGroup(models.TextChoices):
        GRAIN     = "grain",     "Зерновые"
        PROTEIN   = "protein",   "Белки"
        VEGETABLE = "vegetable", "Овощи"
        FRUIT     = "fruit",     "Фрукты"
        DAIRY     = "dairy",     "Молочные"
        OIL       = "oil",       "Масла/жиры"
        OTHER     = "other",     "Прочее"

    class ProteinType(models.TextChoices):
        ANIMAL = "animal", "Животный"
        PLANT  = "plant",  "Растительный"
        MIXED  = "mixed",  "Смешанный"

    class GrainType(models.TextChoices):
        WHOLE   = "whole",   "Цельнозерновые"
        REFINED = "refined", "Рафинированные"

    food_group    = models.CharField(max_length=16, choices=FoodGroup.choices, null=True, blank=True)
    suitable_for  = models.JSONField(default=list, blank=True)
    povar_raw     = models.JSONField(blank=True, null=True)
    protein_type  = models.CharField(max_length=8, choices=ProteinType.choices, null=True, blank=True)
    grain_type    = models.CharField(max_length=8, choices=GrainType.choices, null=True, blank=True)
    is_fatty_fish = models.BooleanField(default=False)
    is_red_meat   = models.BooleanField(default=False)
    kcal     = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True, help_text='Калорийность на 1 порцию, ккал (MG-104d-4).')
    proteins = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text='Белки на 1 порцию, г.')
    fats     = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text='Жиры на 1 порцию, г.')
    carbs    = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text='Углеводы на 1 порцию, г.')

    class Meta:
        db_table = "recipes"
        indexes = [
            models.Index(fields=["legacy_id"]),
            models.Index(fields=["country"]),
            models.Index(fields=["author_id"]),
            models.Index(fields=["is_custom"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["food_group"]),
            models.Index(fields=["protein_type"]),
            models.Index(fields=["grain_type"]),
            models.Index(fields=["is_fatty_fish"]),
            models.Index(fields=["is_red_meat"]),
            GinIndex(fields=["suitable_for"], name="recipe_suitable_for_gin"),
        ]

    def __str__(self):
        return self.title


class RecipeAuthor(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонён"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="author_profile")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    motivation_text = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    recipes_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "recipe_authors"
        indexes = [models.Index(fields=["user_id"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Author({self.user}, {self.status})"


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
