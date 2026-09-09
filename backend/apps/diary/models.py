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


# MG_HEADKEEPS: кто внёс запись.
#
# Дневник, вода и вес заводились только собой, и поля «кем внесено» не
# требовалось: владелец и автор — один человек. Теперь глава семьи может внести
# запись за участника (ребёнок не ведёт дневник сам, у пожилого не всегда
# получается), и разница становится видимой: строка принадлежит участнику, а
# внёс её другой.
#
# Поле необязательное, и пустое значит «внёс сам владелец» — так у всех
# записей, сделанных до этой задачи, и переписывать их незачем. SET_NULL, а не
# CASCADE: глава уйдёт из проекта, а запись участника — его собственная и
# должна остаться.
def added_by_field():
    return models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Кто внёс запись, если не сам владелец (MG_HEADKEEPS).",
    )


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

    class MealSlot(models.TextChoices):
        """MG_MEALSLOT: точное место приёма в дне.

        `meal_type` отвечает на вопрос «какого рода эта еда» — по нему подбираются
        рецепты и считается запрет на сладкое. Перекус там один, и это правильно:
        для подбора первый и второй перекус ничем не отличаются.

        Человеку же в дневнике нужно другое: при пяти приёмах в день перекусов
        два, они в разное время и с разной едой, и сваленные в одну кучу читаются
        плохо. Раскладка дня — отдельный вопрос от рода еды, поэтому и поле
        отдельное. Ровно так же устроен `MenuItem.meal_slot`, откуда слот и
        приходит при заполнении дневника из меню.

        Разъехаться эти два поля не могут: `save()` выводит одно из другого (см.
        ниже). Дважды в этом проекте разметка расходилась с раскладкой, и оба
        раза это стоило недостижимых рецептов — повторять не будем.
        """

        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK1 = "snack1", "Перекус 1"
        SNACK2 = "snack2", "Перекус 2"

    # Слот → род еды. Единственный источник правды о связи этих двух полей.
    SLOT_TO_MEAL_TYPE = {
        "breakfast": "breakfast",
        "lunch": "lunch",
        "dinner": "dinner",
        "snack1": "snack",
        "snack2": "snack",
    }
    # Род еды → слот по умолчанию, когда слот не задан (старые записи, старые
    # клиенты). Перекус попадает в первый: какой он был на самом деле, не знает
    # никто, а первый — единственная догадка, которую человек увидит и поправит.
    MEAL_TYPE_TO_SLOT = {
        "breakfast": "breakfast",
        "lunch": "lunch",
        "dinner": "dinner",
        "snack": "snack1",
    }

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
    # MG_MEALSLOT: см. MealSlot выше. Пустым не остаётся — заполняется в save().
    meal_slot = models.CharField(max_length=20, choices=MealSlot.choices, blank=True, default="")
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True)
    custom_name = models.CharField(max_length=255, blank=True)
    nutrition = models.JSONField(default=dict)
    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    # MG_DIARYGRAMS: сколько съедено, граммов на одну порцию.
    #
    # Вес до сих пор нигде не хранился — он вшивался в название («Творог, 120 г»),
    # и поправить его было нельзя: КБЖУ пересчитать не из чего, а разбирать
    # название строкой — гадание. Поле необязательное: у старых записей веса нет,
    # и у тех, что считаются порциями (рецепт «1 порция»), его тоже может не быть.
    #
    # Общий вес записи = grams × quantity, как и КБЖУ: nutrition хранится на одну
    # порцию, а quantity — множитель.
    grams = models.PositiveIntegerField(null=True, blank=True)
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
    added_by = added_by_field()  # MG_HEADKEEPS
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "diary_entries"
        indexes = [
            models.Index(fields=["user_id", "date"]),
            models.Index(fields=["member_id", "date"]),
            models.Index(fields=["date", "meal_type"]),
        ]

    def save(self, *args, **kwargs):
        """MG_MEALSLOT: держим слот и род еды согласованными.

        Задали слот — род еды выводится из него. Задали только род (старый
        клиент, старый код) — слот получает значение по умолчанию. Разъехаться
        они не могут, и проверять это в каждой ручке не нужно.
        """
        if self.meal_slot:
            derived = self.SLOT_TO_MEAL_TYPE.get(self.meal_slot)
            if derived and derived != self.meal_type:
                self.meal_type = derived
                self._add_update_field(kwargs, "meal_type")
        elif self.meal_type:
            self.meal_slot = self.MEAL_TYPE_TO_SLOT.get(self.meal_type, "")
            self._add_update_field(kwargs, "meal_slot")
        super().save(*args, **kwargs)

    @staticmethod
    def _add_update_field(kwargs, name):
        """Поле, поправленное в save(), должно попасть в update_fields."""
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and name not in update_fields:
            kwargs["update_fields"] = list(update_fields) + [name]

    def __str__(self):
        return f"Diary({self.user}, {self.date}, {self.meal_slot or self.meal_type})"


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
    added_by = added_by_field()  # MG_HEADKEEPS

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
    added_by = added_by_field()  # MG_HEADKEEPS
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


class BodyMeasurement(OwnedByPerson):
    """MG_BODYSIZE: обхваты тела по датам.

    Зачем отдельная таблица, а не пять полей в профиле. Профиль хранит текущее
    состояние и перезаписывается — ровно так когда-то хранился вес, и вопрос
    «что происходит на этом калораже» ответа не имел (см. WeightLog). С
    обхватами это заметнее, чем с весом: вес на сушке стоит неделями, а талия в
    это время уходит, и без прошлых замеров человек решает, что усилия впустую.

    Устройство намеренно повторяет WeightLog: владелец — человек, место записи —
    семья, одна строка на дату (перемерился — правится, а не добавляется
    вторая), запись переживает уход из семьи.

    Все пять обхватов необязательны: кто-то меряет только талию, и заставлять
    его выдумывать шею неправильно. Пустая со всех сторон запись смысла не
    имеет — это проверяет сериализатор, а не база: у базы нет способа сказать
    об этом человеку по-русски.

    Сантиметры дробные (98.5 — обычный результат замера), максимум 999.9: это
    заведомо больше любого человеческого обхвата и заведомо меньше опечатки
    вроде роста в миллиметрах.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="body_measurements")
    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="body_measurements",
    )
    date = models.DateField()
    neck_cm = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    chest_cm = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    under_bust_cm = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    waist_cm = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    hips_cm = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    added_by = added_by_field()  # MG_HEADKEEPS
    created_at = models.DateTimeField(auto_now_add=True)

    # Порядок сверху вниз по телу — в нём поля и показываются, и он же задаёт
    # порядок обходов в коде, чтобы списки нигде не разъезжались.
    FIELDS = ("neck_cm", "chest_cm", "under_bust_cm", "waist_cm", "hips_cm")

    class Meta:
        db_table = "body_measurements"
        unique_together = [("user", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user_id", "-date"]),
            models.Index(fields=["member_id", "-date"]),
        ]

    def __str__(self):
        return f"Body({self.user}, {self.date})"
