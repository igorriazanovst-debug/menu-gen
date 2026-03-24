import hashlib
import hmac
import json
import logging

from decouple import config
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from .models import Payment
from .serializers import PaymentSerializer

log = logging.getLogger(__name__)


def _get_family(user):
    m = FamilyMember.objects.filter(user=user).select_related("family").first()
    return m.family if m else None


class PaymentHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer

    def get_queryset(self):
        family = _get_family(self.request.user)
        if not family:
            return Payment.objects.none()
        return Payment.objects.filter(family=family).order_by("-created_at")


class YookassaWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        # ЮKassa подписывает тело HMAC-SHA256
        signature = request.headers.get("X-Yookassa-Signature", "")
        secret = config("YOOKASSA_SECRET_KEY", default="")
        body = request.body

        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            log.warning("YooKassa webhook: invalid signature")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get("event")
        obj = event.get("object", {})

        if event_type == "payment.succeeded":
            _handle_payment_succeeded(obj)
        elif event_type == "payment.canceled":
            _handle_payment_canceled(obj)
        elif event_type == "refund.succeeded":
            _handle_refund(obj)
        else:
            log.info("YooKassa webhook: unhandled event %s", event_type)

        return Response(status=status.HTTP_200_OK)


# ── handlers ──────────────────────────────────────────────────────────────────

def _handle_payment_succeeded(obj: dict):
    payment_id = obj.get("id")
    metadata = obj.get("metadata", {})
    family_id = metadata.get("family_id")
    plan_code = metadata.get("plan_code")

    if not family_id or not plan_code:
        log.error("YooKassa webhook: missing metadata family_id/plan_code")
        return

    try:
        family = Family.objects.get(id=family_id)
        plan = SubscriptionPlan.objects.get(code=plan_code)
    except (Family.DoesNotExist, SubscriptionPlan.DoesNotExist) as e:
        log.error("YooKassa webhook: %s", e)
        return

    import datetime
    from dateutil.relativedelta import relativedelta

    now = timezone.now()
    if plan.period == SubscriptionPlan.Period.MONTH:
        expires = now + relativedelta(months=1)
    else:
        expires = now + relativedelta(years=1)

    sub = Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=now,
        expires_at=expires,
        auto_renew=True,
    )
    amount_value = obj.get("amount", {}).get("value", "0")
    Payment.objects.create(
        subscription=sub,
        family=family,
        amount=amount_value,
        status=Payment.Status.SUCCEEDED,
        payment_id=payment_id,
        paid_at=now,
    )
    log.info("Subscription created: family=%s plan=%s", family_id, plan_code)


def _handle_payment_canceled(obj: dict):
    payment_id = obj.get("id")
    Payment.objects.filter(payment_id=payment_id).update(status=Payment.Status.CANCELLED)
    log.info("Payment cancelled: %s", payment_id)


def _handle_refund(obj: dict):
    payment_id = obj.get("payment_id")
    Payment.objects.filter(payment_id=payment_id).update(status=Payment.Status.REFUNDED)
    log.info("Refund for payment: %s", payment_id)
