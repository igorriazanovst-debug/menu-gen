from rest_framework import serializers

from .models import BodyMeasurement, DiaryEntry, WaterLog, WeightLog


class AddedByMixin(serializers.ModelSerializer):
    """MG_HEADKEEPS: кто внёс запись, если не сам владелец.

    Клиенту нужно имя, а не идентификатор: он рисует рядом со строкой корону и
    подпись «внесла Ольга». Пустое поле значит «внёс сам» — так у всех записей,
    сделанных до этой задачи, и отдельного признака для них не требуется.
    """

    added_by_name = serializers.CharField(source="added_by.name", read_only=True, default=None)

    def _author(self):
        # Автора кладёт вид: только он знает, кто пришёл и за кого пишет.
        return self.context.get("author")


class DiaryEntrySerializer(AddedByMixin):
    recipe_title = serializers.CharField(source="recipe.title", read_only=True, default=None)

    class Meta:
        model = DiaryEntry
        fields = (
            "id",
            "date",
            "meal_type",
            "meal_slot",  # MG_MEALSLOT: точное место приёма в дне
            "recipe",
            "recipe_title",
            "custom_name",
            "nutrition",
            "quantity",
            "grams",  # MG_DIARYGRAMS: сколько съедено, г на порцию
            "planned_menu_item",  # MG_605B_V_serializers
            "is_eaten",  # MG_605B_V_serializers
            "is_planned",  # DIARY_COPY_V3
            "added_by",  # MG_HEADKEEPS
            "added_by_name",
            "created_at",
        )
        read_only_fields = ("id", "added_by", "added_by_name", "created_at")


class DiaryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaryEntry
        # MG_605B_V_serializers: план-факт
        # MG-605.C: используется и для POST, и для PATCH (через partial=True)
        fields = (
            "date",
            "meal_type",
            "meal_slot",  # MG_MEALSLOT: клиент присылает слот, род еды выводится
            "recipe",
            "custom_name",
            "nutrition",
            "quantity",
            "grams",  # MG_DIARYGRAMS
            "planned_menu_item",
            "is_eaten",
            "is_planned",  # DIARY_COPY_V3
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # MG_MEALSLOT: клиенту достаточно прислать слот — род еды выводится из
        # него. Обязательным meal_type остаться не может: иначе новый экран
        # дневника был бы обязан дублировать то, что и так известно, а
        # рассогласование этих двух полей мы как раз и убираем.
        self.fields["meal_type"].required = False

    def validate_meal_slot(self, value):
        # Пустой слот допустим — модель выведет его из meal_type.
        return value or ""

    def validate(self, attrs):
        # MG-605.C: на PATCH (partial) валидируем «recipe или custom_name»
        # с учётом instance — иначе любой PATCH без recipe ронял бы запись.
        recipe = attrs.get("recipe", getattr(self.instance, "recipe", None))
        custom_name = attrs.get("custom_name", getattr(self.instance, "custom_name", ""))
        if not recipe and not custom_name:
            raise serializers.ValidationError("Укажите рецепт или название блюда.")

        # MG_MEALSLOT: одно из двух должно быть — иначе непонятно, куда класть.
        # На PATCH достаточно того, что уже стоит в записи.
        meal_type = attrs.get("meal_type", getattr(self.instance, "meal_type", ""))
        meal_slot = attrs.get("meal_slot", getattr(self.instance, "meal_slot", ""))
        if not meal_type and not meal_slot:
            raise serializers.ValidationError("Укажите приём пищи.")
        return attrs

    def create(self, validated_data):
        member = self.context["member"]
        if not validated_data.get("nutrition") and validated_data.get("recipe"):
            validated_data["nutrition"] = validated_data["recipe"].nutrition or {}
        # MG_OWNDIARY: владелец — человек, членство — пометка «за каким столом».
        # MG_HEADKEEPS: автор — если писал не владелец.
        return DiaryEntry.objects.create(
            user=member.user,
            member=member,
            added_by=self.context.get("author"),
            **validated_data,
        )


# MG_605D_V_serializers: вложенная структура план/факт.
class _NutritionBucketSerializer(serializers.Serializer):
    calories = serializers.FloatField()
    proteins = serializers.FloatField()
    fats = serializers.FloatField()
    carbs = serializers.FloatField()


class DiaryStatsDaySerializer(serializers.Serializer):
    """MG-605.D: возвращает {date, planned, actual, total}.

    - planned: суммы по записям с planned_menu_item IS NOT NULL
    - actual:  суммы по записям, считающимся «съеденными»:
               is_eaten = True ИЛИ planned_menu_item IS NULL
               (вручную добавленное считаем фактом сразу; плановое — только после галочки)
    - total:   синоним actual (для UI прогресс-бара)
    """

    date = serializers.DateField()
    planned = _NutritionBucketSerializer()
    actual = _NutritionBucketSerializer()
    total = _NutritionBucketSerializer()


# Обратная совместимость на случай внешних импортов.
DiaryStatsSerializer = DiaryStatsDaySerializer


class DiaryImportSerializer(serializers.Serializer):
    """MG-605.D: query-params для POST /diary/import-from-menu/."""

    menu_id = serializers.IntegerField()
    date = serializers.DateField()
    # FILL_FROM_MENU_V4: optional subset of MenuItem ids to import (empty/None = whole menu).
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)


class WaterLogSerializer(AddedByMixin):
    class Meta:
        model = WaterLog
        fields = ("id", "date", "water_ml", "added_by", "added_by_name")
        read_only_fields = ("id", "added_by", "added_by_name")

    def create(self, validated_data):
        member = self.context["member"]
        # MG_OWNDIARY: день у человека один, за сколькими бы столами он ни сидел.
        obj, _ = WaterLog.objects.get_or_create(
            user=member.user,
            date=validated_data["date"],
            defaults={"water_ml": 0, "member": member},
        )
        obj.water_ml = validated_data["water_ml"]
        obj.member = member
        # MG_HEADKEEPS: у воды на день одна строка, и правит её то тот, то этот.
        # Корона показывает, кто поставил ТЕКУЩЕЕ значение, поэтому автор
        # переписывается при каждой записи — в том числе на None, когда человек
        # сам поправил то, что за него внесли.
        obj.added_by = self._author()
        obj.save(update_fields=["water_ml", "member", "added_by"])
        return obj


class WeightLogSerializer(AddedByMixin):
    """MG_TRAINER: точка замера веса. На дату — одна запись."""

    class Meta:
        model = WeightLog
        fields = ("id", "date", "weight_kg", "note", "added_by", "added_by_name")
        read_only_fields = ("id", "added_by", "added_by_name")

    def validate_weight_kg(self, value):
        if value <= 0 or value > 500:
            raise serializers.ValidationError("Вес должен быть в пределах 0–500 кг.")
        return value

    def create(self, validated_data):
        member = self.context["member"]
        # MG_OWNDIARY: замер принадлежит человеку; членство — где он записан.
        obj, _ = WeightLog.objects.update_or_create(
            user=member.user,
            date=validated_data["date"],
            defaults={
                "weight_kg": validated_data["weight_kg"],
                "note": validated_data.get("note", ""),
                "member": member,
                # MG_HEADKEEPS: как и у воды — чьё текущее значение, тот и автор.
                "added_by": self._author(),
            },
        )
        return obj


class BodyMeasurementSerializer(AddedByMixin):
    """MG_BODYSIZE: обхваты за дату. На дату — одна запись, как у веса."""

    class Meta:
        model = BodyMeasurement
        fields = (
            "id",
            "date",
            "neck_cm",
            "chest_cm",
            "under_bust_cm",
            "waist_cm",
            "hips_cm",
            "note",
            "added_by",
            "added_by_name",
        )
        read_only_fields = ("id", "added_by", "added_by_name")

    # Границы намеренно широкие: это защита от опечатки (рост вместо талии,
    # миллиметры вместо сантиметров), а не медицинская норма. Судить о том,
    # бывает ли талия 55 см, — не дело формы ввода.
    def _check(self, value, name):
        if value is None:
            return value
        if value <= 0 or value > 300:
            raise serializers.ValidationError(f"{name} должен быть в пределах 0–300 см.")
        return value

    def validate_neck_cm(self, v):
        return self._check(v, "Обхват шеи")

    def validate_chest_cm(self, v):
        return self._check(v, "Обхват груди")

    def validate_under_bust_cm(self, v):
        return self._check(v, "Обхват под грудью")

    def validate_waist_cm(self, v):
        return self._check(v, "Обхват талии")

    def validate_hips_cm(self, v):
        return self._check(v, "Обхват бёдер")

    def validate(self, attrs):
        # Пустая со всех сторон запись — не замер, а строка с датой. Проверяем
        # с учётом уже сохранённого: PATCH одного поля не должен требовать
        # прислать остальные четыре.
        values = [attrs.get(f, getattr(self.instance, f, None)) for f in BodyMeasurement.FIELDS]
        if not any(v is not None for v in values):
            raise serializers.ValidationError("Укажите хотя бы один обхват.")
        return attrs

    def create(self, validated_data):
        member = self.context["member"]
        date = validated_data.pop("date")
        # MG_OWNDIARY: замер принадлежит человеку; членство — где он записан.
        # update_or_create, а не create: перемерился в тот же день — правим
        # запись, а не заводим вторую (так же устроен вес).
        obj, _ = BodyMeasurement.objects.update_or_create(
            user=member.user,
            date=date,
            defaults={**validated_data, "member": member, "added_by": self._author()},
        )
        return obj


# DIARY_COPY_V3: body for POST /diary/copy/.
class DiaryCopySerializer(serializers.Serializer):
    entry_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=200)
    target_date = serializers.DateField()
