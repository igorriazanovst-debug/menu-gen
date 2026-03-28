from django.db import models
from apps.users.models import User


class Recipe(models.Model):
    legacy_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    cook_time = models.CharField(max_length=64, null=True, blank=True)
    servings = models.PositiveSmallIntegerField(null=True, blank=True)
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

    class Meta:
        db_table = "recipes"
        indexes = [
            models.Index(fields=["legacy_id"]),
            models.Index(fields=["country"]),
            models.Index(fields=["author_id"]),
            models.Index(fields=["is_custom"]),
            models.Index(fields=["is_published"]),
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
