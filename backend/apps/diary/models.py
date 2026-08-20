from django.db import models

from apps.family.models import FamilyMember

# MG_605B_V_models: связь дневник→меню (план-факт)
from apps.menu.models import MenuItem
from apps.recipes.models import Recipe


class DiaryEntry(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK = "snack", "Перекус"

    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name="diary_entries")
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True)
    custom_name = models.CharField(max_length=255, blank=True)
    nutrition = models.JSONField(default=dict)
    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    # MG_605B_V_models: план-факт (OneToOne — один план → один факт)
    planned_menu_item = models.OneToOneField(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diary_entry",
    )
    is_eaten = models.BooleanField(default=False)
    # DIARY_COPY_V3: explicit plan flag, decoupled from planned_menu_item source.
    is_planned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "diary_entries"
        indexes = [
            models.Index(fields=["member_id", "date"]),
            models.Index(fields=["date", "meal_type"]),
        ]

    def __str__(self):
        return f"Diary({self.member}, {self.date}, {self.meal_type})"


class WaterLog(models.Model):
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name="water_logs")
    date = models.DateField()
    water_ml = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "water_logs"
        unique_together = [("member", "date")]


class WeightLog(models.Model):
    """MG_TRAINER: вес по датам.

    В профиле вес — одно число, оно перезаписывается: истории нет, и главный
    вопрос тренера «что происходит с весом на этом калораже» ответа не имеет.
    Здесь — точки замеров, по одной на дату (перевзвесился — запись правится,
    а не добавляется вторая).

    Устройство намеренно повторяет WaterLog: тот же владелец (участник семьи),
    та же уникальность по дню, та же простота.
    """

    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name="weight_logs")
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weight_logs"
        unique_together = [("member", "date")]
        ordering = ["-date"]
        indexes = [models.Index(fields=["member_id", "-date"])]

    def __str__(self):
        return f"Weight({self.member}, {self.date}, {self.weight_kg})"
