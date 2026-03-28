from django.db import models

from apps.family.models import Family, FamilyMember
from apps.recipes.models import Recipe


class Menu(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Активно"
        ARCHIVED = "archived", "Архив"

    class ModifiedBy(models.TextChoices):
        USER = "user", "Пользователь"
        SPECIALIST = "specialist", "Специалист"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="menus")
    creator_id = models.BigIntegerField()
    period_days = models.PositiveSmallIntegerField(default=7)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    modified_by = models.CharField(max_length=20, choices=ModifiedBy.choices, default=ModifiedBy.USER)
    filters_used = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menus"
        indexes = [
            models.Index(fields=["family_id", "status"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["creator_id"]),
        ]

    def __str__(self):
        return f"Menu({self.family}, {self.start_date}–{self.end_date})"


class MenuItem(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK = "snack", "Перекус"

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, null=True, blank=True)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    day_offset = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)

    class Meta:
        db_table = "menu_items"
        unique_together = [("menu", "member", "day_offset", "meal_type")]
        indexes = [
            models.Index(fields=["menu_id"]),
            models.Index(fields=["recipe_id"]),
            models.Index(fields=["member_id"]),
        ]

    def __str__(self):
        return f"{self.menu} / day {self.day_offset} / {self.meal_type}"


class ShoppingList(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="shopping_lists")
    menu = models.ForeignKey(Menu, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shopping_lists"


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    product_id = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_purchased = models.BooleanField(default=False)
    purchased_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "shopping_items"
        indexes = [
            models.Index(fields=["shopping_list_id", "is_purchased"]),
            models.Index(fields=["category"]),
        ]
