from django.db import models

from apps.family.models import FamilyMember

# MG_605B_V_models: связь дневник→меню (план-факт)
from apps.menu.models import MenuItem
from apps.recipes.models import Recipe
from apps.users.models import User

# MG_OWNDIARY: у дневника, воды и веса два разных вопроса, и раньше на оба
# отвечало одно поле `member`.
#
# «Чьё это» — вопрос про человека. Еда, вода и особенно вес принадлежат ему, а не
# столу, за которым он в тот день сидел. Пока владельцем было членство в семье,
# выходило две неприятности. Первая: человек, состоящий в двух семьях, имел две
# несвязанные истории, и при переключении семьи (T-26) его замеры веса пропадали
# бы с экрана. Вторая, уже действующая: исключение из семьи удаляло членство, а
# вместе с ним каскадом — весь дневник, всю воду и все замеры веса. Человека
# выводили из-за стола и стирали ему историю питания.
#
# «Где это записано» — вопрос про семью, и он тоже нужен: по нему специалист
# видит своего клиента, а глава семьи — то, что происходило за его столом.
#
# Поэтому полей теперь два. Владелец — `user`, обязательный. Место записи —
# `member`, необязательное и с SET_NULL: ушёл из семьи — история осталась при
# человеке, а из семейных отчётов пропала.


class OwnedByPerson(models.Model):
    """MG_OWNDIARY: общая часть трёх таблиц — владелец человек, место записи семья.

    Строку по-прежнему можно адресовать одним членством: владельца выведем сами,
    `member.user` — это он и есть, другого ответа быть не может. Нужно это не для
    красоты, а чтобы перенос не разъехался: код, писавший `member=...` до этой
    задачи, продолжает работать и создаёт правильные строки, а не падает на
    обязательном поле в неожиданном месте.

    Обратное неверно: `member` из `user` не выводится — в какой семье сделана
    запись, знает только тот, кто её делает.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.user_id is None and self.member_id is not None:
            self.user_id = self.member.user_id
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list(update_fields) + ["user"]
        super().save(*args, **kwargs)


class DiaryEntry(OwnedByPerson):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK = "snack", "Перекус"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="diary_entries")
    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diary_entries",
    )
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
            models.Index(fields=["user_id", "date"]),
            models.Index(fields=["member_id", "date"]),
            models.Index(fields=["date", "meal_type"]),
        ]

    def __str__(self):
        return f"Diary({self.user}, {self.date}, {self.meal_type})"


class WaterLog(OwnedByPerson):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="water_logs")
    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="water_logs",
    )
    date = models.DateField()
    water_ml = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "water_logs"
        # MG_OWNDIARY: день у человека один, за сколькими бы столами он ни сидел.
        unique_together = [("user", "date")]


class WeightLog(OwnedByPerson):
    """MG_TRAINER: вес по датам.

    В профиле вес — одно число, оно перезаписывается: истории нет, и главный
    вопрос тренера «что происходит с весом на этом калораже» ответа не имеет.
    Здесь — точки замеров, по одной на дату (перевзвесился — запись правится,
    а не добавляется вторая).

    Устройство намеренно повторяет WaterLog: тот же владелец (участник семьи),
    та же уникальность по дню, та же простота.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="weight_logs")
    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weight_logs",
    )
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weight_logs"
        # MG_OWNDIARY: вес — величина человека, а не его места за столом.
        unique_together = [("user", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user_id", "-date"]),
            models.Index(fields=["member_id", "-date"]),
        ]

    def __str__(self):
        return f"Weight({self.member}, {self.date}, {self.weight_kg})"
