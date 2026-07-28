import hashlib
import hmac
import json
import logging
from urllib.parse import urlencode

from decouple import config
from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.utils import timezone
from django.utils.html import escape
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
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
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
        from django.conf import settings as django_settings

        secret = getattr(django_settings, "YOOKASSA_SECRET_KEY", config("YOOKASSA_SECRET_KEY", default=""))
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


# ── MG_PAYSTUB: тестовая заглушка оплаты (имитация ЮMoney) ────────────────────


def _append_query(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def stub_checkout(request):
    """Тестовая страница «оплаты» — имитирует redirect-страницу ЮKassa."""
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    p = request.GET
    keep = {k: p.get(k, "") for k in ("payment_id", "family_id", "plan_code", "amount", "return_url")}
    q = urlencode(keep)
    confirm_url = f"/api/v1/payments/stub/confirm/?{q}"
    cancel_url = f"/api/v1/payments/stub/cancel/?{q}"
    amount = escape(keep["amount"] or "—")
    plan = escape(keep["plan_code"] or "—")
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Тестовая оплата</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f7f5f2;margin:0;
   min-height:100vh;display:flex;align-items:center;justify-content:center;color:#3a2e26}}
 .card{{background:#fff;border-radius:20px;box-shadow:0 10px 40px rgba(0,0,0,.08);
   padding:32px;max-width:380px;width:90%;text-align:center}}
 .logo{{font-size:44px}} h1{{font-size:20px;margin:12px 0 4px}}
 .muted{{color:#9b8f86;font-size:14px}} .amount{{font-size:30px;font-weight:700;margin:16px 0}}
 .badge{{display:inline-block;background:#fdecec;color:#c0392b;border-radius:8px;
   padding:2px 8px;font-size:12px;margin-bottom:8px}}
 a.btn{{display:block;text-decoration:none;border-radius:12px;padding:12px;margin-top:10px;font-weight:600}}
 .pay{{background:#e5533c;color:#fff}} .cancel{{background:#efe9e4;color:#6b5d53}}
</style></head><body><div class="card">
 <div class="badge">ТЕСТОВЫЙ РЕЖИМ (заглушка)</div>
 <div class="logo">🍅</div>
 <h1>Оплата подписки</h1>
 <div class="muted">Тариф: {plan}</div>
 <div class="amount">{amount} ₽</div>
 <a class="btn pay" href="{confirm_url}">Оплатить</a>
 <a class="btn cancel" href="{cancel_url}">Отменить</a>
 <p class="muted" style="margin-top:16px">Это имитация страницы ЮKassa. Реальные деньги не списываются.</p>
</div></body></html>"""
    return HttpResponse(html)


def stub_confirm(request):
    """Имитация успешного платежа: прогоняем тот же обработчик, что и вебхук."""
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    p = request.GET
    payment_id = p.get("payment_id", "")
    return_url = p.get("return_url", "/")
    # Идемпотентность: повторный переход не создаёт вторую подписку.
    already = payment_id and Payment.objects.filter(payment_id=payment_id, status=Payment.Status.SUCCEEDED).exists()
    if not already:
        obj = {
            "id": payment_id,
            "status": "succeeded",
            "paid": True,
            "amount": {"value": p.get("amount", "0"), "currency": "RUB"},
            "metadata": {"family_id": p.get("family_id"), "plan_code": p.get("plan_code")},
        }
        _handle_payment_succeeded(obj)
    return HttpResponseRedirect(_append_query(return_url, "payment", "success"))


def stub_cancel(request):
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    return_url = request.GET.get("return_url", "/")
    return HttpResponseRedirect(_append_query(return_url, "payment", "cancel"))


def _handle_payment_canceled(obj: dict):
    payment_id = obj.get("id")
    Payment.objects.filter(payment_id=payment_id).update(status=Payment.Status.CANCELLED)
    log.info("Payment cancelled: %s", payment_id)


def _handle_refund(obj: dict):
    payment_id = obj.get("payment_id")
    Payment.objects.filter(payment_id=payment_id).update(status=Payment.Status.REFUNDED)
    log.info("Refund for payment: %s", payment_id)
