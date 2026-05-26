from rest_framework import serializers

from .models import DiaryEntry, WaterLog


class DiaryEntrySerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source="recipe.title", read_only=True, default=None)

    class Meta:
        model = DiaryEntry
        fields = (
            "id",
            "date",
            "meal_type",
            "recipe",
            "recipe_title",
            "custom_name",
            "nutrition",
            "quantity",
            "planned_menu_item",  # MG_605B_V_serializers
            "is_eaten",  # MG_605B_V_serializers
            "is_planned",  # DIARY_COPY_V3
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class DiaryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaryEntry
        # MG_605B_V_serializers: план-факт
        # MG-605.C: используется и для POST, и для PATCH (через partial=True)
        fields = (
            "date",
            "meal_type",
            "recipe",
            "custom_name",
            "nutrition",
            "quantity",
            "planned_menu_item",
            "is_eaten",
            "is_planned",  # DIARY_COPY_V3
        )

    def validate(self, attrs):
        # MG-605.C: на PATCH (partial) валидируем «recipe или custom_name»
        # с учётом instance — иначе любой PATCH без recipe ронял бы запись.
        recipe = attrs.get("recipe", getattr(self.instance, "recipe", None))
        custom_name = attrs.get("custom_name", getattr(self.instance, "custom_name", ""))
        if not recipe and not custom_name:
            raise serializers.ValidationError("Укажите рецепт или название блюда.")
        return attrs

    def create(self, validated_data):
        member = self.context["member"]
        if not validated_data.get("nutrition") and validated_data.get("recipe"):
            validated_data["nutrition"] = validated_data["recipe"].nutrition or {}
        return DiaryEntry.objects.create(member=member, **validated_data)


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


class WaterLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterLog
        fields = ("id", "date", "water_ml")
        read_only_fields = ("id",)

    def create(self, validated_data):
        member = self.context["member"]
        obj, _ = WaterLog.objects.get_or_create(
            member=member,
            date=validated_data["date"],
            defaults={"water_ml": 0},
        )
        obj.water_ml = validated_data["water_ml"]
        obj.save(update_fields=["water_ml"])
        return obj


# DIARY_COPY_V3: body for POST /diary/copy/.
class DiaryCopySerializer(serializers.Serializer):
    entry_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=200
    )
    target_date = serializers.DateField()
