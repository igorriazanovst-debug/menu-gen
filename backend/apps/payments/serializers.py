from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(
        source="subscription.plan.name", read_only=True, default=None
    )

    class Meta:
        model = Payment
        fields = ("id", "amount", "currency", "status", "provider", "plan_name", "paid_at", "created_at")
