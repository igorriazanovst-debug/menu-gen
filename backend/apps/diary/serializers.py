from rest_framework import serializers
from .models import DiaryEntry, WaterLog


class DiaryEntrySerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source="recipe.title", read_only=True, default=None)

    class Meta:
        model = DiaryEntry
        fields = (
            "id", "date", "meal_type", "recipe", "recipe_title",
            "custom_name", "nutrition", "quantity", "created_at",
        )
        read_only_fields = ("id", "created_at")


class DiaryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaryEntry
        fields = ("date", "meal_type", "recipe", "custom_name", "nutrition", "quantity")

    def validate(self, attrs):
        if not attrs.get("recipe") and not attrs.get("custom_name"):
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
            member=member, date=validated_data["date"],
            defaults={"water_ml": 0},
        )
        obj.water_ml = validated_data["water_ml"]
        obj.save(update_fields=["water_ml"])
        return obj
