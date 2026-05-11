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
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class DiaryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaryEntry
        # MG_605B_V_serializers: план-факт
        # MG-605.C: используется и для POST, и для PATCH (через partial=True)
        fields = (
            "date", "meal_type", "recipe", "custom_name",
            "nutrition", "quantity", "planned_menu_item", "is_eaten",
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


class DiaryStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    calories = serializers.FloatField()
    proteins = serializers.FloatField()
    fats = serializers.FloatField()
    carbs = serializers.FloatField()


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
