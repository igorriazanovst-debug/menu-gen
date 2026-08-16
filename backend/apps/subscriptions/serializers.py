from rest_framework import serializers

from .models import PlanOffer, Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "code", "name", "price", "period", "features", "max_family_members")


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ("id", "plan", "status", "started_at", "expires_at", "auto_renew")


class PlanOfferSerializer(serializers.ModelSerializer):
    """MG_PAYPERIOD: вариант покупки — период, цена и выгода относительно месяца."""

    plan_code = serializers.CharField(source="plan.code", read_only=True)
    price_per_month = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = PlanOffer
        fields = ("code", "title", "months", "price", "price_per_month", "discount_percent", "plan_code")

    def get_discount_percent(self, obj):
        """Насколько дешевле месяца при помесячной оплате. 0 — если не дешевле.

        Считаем на бэкенде: скидка должна быть одинаковой в вебе и в мобильном,
        а не пересчитываться в каждом клиенте по-своему.
        """
        base = self.context.get("monthly_price")
        if not base or not obj.months or obj.months <= 1:
            return 0
        full = base * obj.months
        if full <= 0 or obj.price >= full:
            return 0
        return int(round((full - obj.price) / full * 100))


class SubscribeSerializer(serializers.Serializer):
    # MG_PAYPERIOD: покупается период (offer_code). plan_code оставлен ради
    # уже установленных сборок мобильного — там выбора периода ещё нет.
    offer_code = serializers.CharField(required=False)
    plan_code = serializers.CharField(required=False)
    return_url = serializers.URLField()

    def validate(self, attrs):
        offer = None
        if attrs.get("offer_code"):
            offer = PlanOffer.objects.filter(code=attrs["offer_code"], is_active=True).select_related("plan").first()
            if offer is None:
                raise serializers.ValidationError({"offer_code": "Период не найден."})
        elif attrs.get("plan_code"):
            offer = (
                PlanOffer.objects.filter(plan__code=attrs["plan_code"], is_active=True)
                .select_related("plan")
                .order_by("months", "price")
                .first()
            )
            if offer is None:
                raise serializers.ValidationError({"plan_code": "Тариф не найден."})
        else:
            raise serializers.ValidationError({"offer_code": "Укажите период подписки."})
        attrs["offer"] = offer
        return attrs


class RedeemPromoSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)
