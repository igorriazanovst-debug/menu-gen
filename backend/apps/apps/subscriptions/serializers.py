from rest_framework import serializers
from .models import Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "code", "name", "price", "period", "features", "max_family_members")


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ("id", "plan", "status", "started_at", "expires_at", "auto_renew")


class SubscribeSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    return_url = serializers.URLField()

    def validate_plan_code(self, value):
        if not SubscriptionPlan.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("Тариф не найден.")
        return value
