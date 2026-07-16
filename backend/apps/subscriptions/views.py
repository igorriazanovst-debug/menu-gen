from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember

from .models import Subscription, SubscriptionPlan
from .promo import PromoError, redeem
from .serializers import RedeemPromoSerializer, SubscribeSerializer, SubscriptionPlanSerializer, SubscriptionSerializer


def _get_family(user):
    m = FamilyMember.objects.filter(user=user).select_related("family").first()
    return m.family if m else None


class SubscriptionPlanListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "price")


class CurrentSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: SubscriptionSerializer})
    def get(self, request):
        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        sub = (
            Subscription.objects.filter(family=family, status=Subscription.Status.ACTIVE)
            .select_related("plan")
            .order_by("-started_at")
            .first()
        )
        if not sub:
            return Response({"detail": "Активная подписка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SubscriptionSerializer(sub).data)


class SubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=SubscribeSerializer,
        responses={200: {"type": "object", "properties": {"payment_url": {"type": "string"}}}},
    )
    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        plan = SubscriptionPlan.objects.get(code=serializer.validated_data["plan_code"])
        return_url = serializer.validated_data["return_url"]

        from apps.payments.yookassa_client import create_payment

        payment_url, payment_id = create_payment(
            amount=float(plan.price),
            description=f"Подписка {plan.name}",
            return_url=return_url,
            metadata={"family_id": family.id, "plan_code": plan.code},
        )
        return Response({"payment_url": payment_url, "payment_id": payment_id})


class CancelSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: None})
    def post(self, request):
        family = _get_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        updated = Subscription.objects.filter(family=family, status=Subscription.Status.ACTIVE).update(auto_renew=False)
        if not updated:
            return Response({"detail": "Активная подписка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Автопродление отключено."})


class RedeemPromoView(APIView):
    """Активация промокода: выдаёт/продлевает премиум-подписку семье пользователя."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=RedeemPromoSerializer, responses={200: SubscriptionSerializer})
    def post(self, request):
        serializer = RedeemPromoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        family = _get_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        try:
            sub = redeem(serializer.validated_data["code"], family, request.user)
        except PromoError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = SubscriptionSerializer(sub).data
        data["detail"] = "Промокод активирован. Премиум подключён."
        return Response(data)
