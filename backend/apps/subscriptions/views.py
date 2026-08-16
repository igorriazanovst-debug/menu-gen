import logging

from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember

from .models import PlanOffer, Subscription, SubscriptionPlan
from .promo import PromoError, redeem
from .serializers import (
    PlanOfferSerializer,
    RedeemPromoSerializer,
    SubscribeSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
)


log = logging.getLogger(__name__)


def _get_family(user):
    m = FamilyMember.objects.filter(user=user).select_related("family").first()
    return m.family if m else None


class SubscriptionPlanListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "price")


class PlanOfferListView(generics.ListAPIView):
    """MG_PAYPERIOD: из чего выбирает пользователь — периоды и цены."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PlanOfferSerializer

    def get_queryset(self):
        return (
            PlanOffer.objects.filter(is_active=True, plan__is_active=True)
            .select_related("plan")
            .order_by("sort_order", "months")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Точка отсчёта для скидки — самый короткий период того же тарифа.
        monthly = self.get_queryset().order_by("months").first()
        ctx["monthly_price"] = monthly.price_per_month if monthly else None
        return ctx


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

        offer = serializer.validated_data["offer"]
        return_url = serializer.validated_data["return_url"]

        # MG_PAYSTUB: реальная ЮKassa или тестовая заглушка (по settings.PAYMENTS_STUB).
        from apps.payments.service import initiate_payment
        from apps.payments.yookassa_client import PaymentsNotConfigured

        try:
            payment_url, payment_id = initiate_payment(family, offer, return_url, user=request.user)
        except PaymentsNotConfigured as exc:
            # Настройки не заполнены — это про сервер, а не про пользователя.
            # Причина уходит в лог, наружу — понятная фраза вместо 500.
            log.error("Оплата не настроена: %s", exc)
            return Response(
                {"detail": "Оплата временно недоступна. Мы уже разбираемся."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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

        code = serializer.validated_data["code"]
        try:
            sub = redeem(code, family, request.user)
        except PromoError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = SubscriptionSerializer(sub).data
        data["detail"] = "Промокод активирован. Премиум подключён."

        # MG_SPECINVITE: код специалиста, кроме премиума, открывает ему доступ к
        # данным семьи. Ввод кода и есть согласие клиента, поэтому отдельного
        # подтверждения не спрашиваем — но говорим об этом прямо.
        from apps.specialists.invites import link_after_redeem

        specialist = link_after_redeem(code, family, request.user)
        if specialist is not None:
            name = specialist.user.name or specialist.user.email
            data["specialist"] = {
                "name": name,
                "type": specialist.specialist_type,
                "type_display": specialist.get_specialist_type_display(),
            }
            data["detail"] = (
                f"Промокод активирован. Премиум подключён, доступ к вашим данным открыт: "
                f"{name} ({specialist.get_specialist_type_display().lower()}). "
                f"Прекратить можно в разделе «Мои специалисты»."
            )
        return Response(data)
