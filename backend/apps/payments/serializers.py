from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="subscription.plan.name", read_only=True, default=None)
    # MG_PAYRELIABLE: что именно куплено и до какой даты продлило — по строке
    # платежа это должно читаться без похода в другие таблицы.
    offer_title = serializers.CharField(source="offer.title", read_only=True, default=None)
    expires_at = serializers.DateTimeField(source="subscription.expires_at", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = (
            "id",
            "payment_id",
            "amount",
            "currency",
            "status",
            "provider",
            "plan_name",
            "offer_title",
            "expires_at",
            "paid_at",
            "created_at",
        )
