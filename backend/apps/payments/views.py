import ipaddress
import json
import logging
from urllib.parse import urlencode

from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.utils.html import escape
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember

from .activation import ActivationError, activate_payment, mark_cancelled, mark_refunded
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


class PaymentStatusView(APIView):
    """MG_PAYRELIABLE: «я вернулся с оплаты, что там?»

    Уведомление может задержаться или потеряться, а человек уже смотрит на
    экран. Здесь мы сами спрашиваем ЮKassa о статусе и, если оплачено,
    выдаём подписку — тем же путём, что и уведомление.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: PaymentSerializer})
    def get(self, request, payment_id: str):
        family = _get_family(request.user)
        payment = Payment.objects.filter(payment_id=payment_id, family=family).first()
        if payment is None:
            return Response({"detail": "Платёж не найден."}, status=status.HTTP_404_NOT_FOUND)

        if payment.status == Payment.Status.PENDING:
            try:
                payment = activate_payment(payment_id) or payment
            except ActivationError as exc:
                log.error("PaymentStatusView: %s", exc)

        return Response(PaymentSerializer(payment).data)


# ── вебхук ────────────────────────────────────────────────────────────────────

# Уведомления ЮKassa приходят с этих адресов. Проверка по IP — первый рубеж;
# второй и главный — перепроверка платежа через API (см. activation).
YOOKASSA_NETWORKS = (
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",
)


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_yookassa_ip(ip: str) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in YOOKASSA_NETWORKS:
        try:
            if addr in ipaddress.ip_network(net):
                return True
        except ValueError:
            continue
    return False


class YookassaWebhookView(APIView):
    """MG_PAYRELIABLE: уведомление ЮKassa.

    Раньше здесь сверялась HMAC-подпись тела на секретном ключе. ЮKassa так
    уведомления не подписывает — проверка отвергала бы вообще все настоящие
    уведомления, то есть деньги списывались бы, а подписка не включалась.

    Теперь из тела берём только идентификатор платежа, а статус и сумму
    спрашиваем у ЮKassa напрямую. Подделать нечего: что бы ни прислали,
    решение принимается по ответу API.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        ip = _client_ip(request)
        if getattr(django_settings, "PAYMENTS_WEBHOOK_CHECK_IP", True) and not is_yookassa_ip(ip):
            log.warning("YooKassa webhook: запрос с постороннего адреса %s", ip)
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            event = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get("event")
        obj = event.get("object") or {}
        payment_id = obj.get("id")

        try:
            if event_type == "payment.succeeded":
                activate_payment(payment_id)
            elif event_type == "payment.canceled":
                mark_cancelled(payment_id)
            elif event_type == "refund.succeeded":
                mark_refunded(obj.get("payment_id"))
            else:
                log.info("YooKassa webhook: событие %s не обрабатывается", event_type)
        except ActivationError as exc:
            # Отвечаем 200: повтор уведомления ничего не изменит, а ЮKassa
            # будет слать его сутками. Разбираться нужно по логу.
            log.error("YooKassa webhook: платёж %s не активирован — %s", payment_id, exc)
        except Exception as exc:  # noqa: BLE001
            # А вот здесь повтор поможет: сеть, недоступный API, дедлок.
            log.error("YooKassa webhook: сбой на платеже %s — %s", payment_id, exc)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)


# ── MG_PAYSTUB: тестовая заглушка оплаты ──────────────────────────────────────


def _append_query(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def stub_checkout(request):
    """Тестовая страница «оплаты» — имитирует redirect-страницу ЮKassa."""
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    p = request.GET
    keep = {k: p.get(k, "") for k in ("payment_id", "offer_code", "amount", "return_url")}
    q = urlencode(keep)
    confirm_url = f"/api/v1/payments/stub/confirm/?{q}"
    cancel_url = f"/api/v1/payments/stub/cancel/?{q}"
    amount = escape(keep["amount"] or "—")
    offer = escape(keep["offer_code"] or "—")
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
 <div class="muted">Период: {offer}</div>
 <div class="amount">{amount} ₽</div>
 <a class="btn pay" href="{confirm_url}">Оплатить</a>
 <a class="btn cancel" href="{cancel_url}">Отменить</a>
 <p class="muted" style="margin-top:16px">Это имитация страницы ЮKassa. Реальные деньги не списываются.</p>
</div></body></html>"""
    return HttpResponse(html)


def stub_confirm(request):
    """Имитация успешного платежа: тот же путь активации, что и у настоящего."""
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    p = request.GET
    payment_id = p.get("payment_id", "")
    return_url = p.get("return_url", "/")
    try:
        activate_payment(payment_id)
    except ActivationError as exc:
        log.error("stub_confirm: %s", exc)
        return HttpResponseRedirect(_append_query(return_url, "payment", "error"))
    return HttpResponseRedirect(_append_query(return_url, "payment", "success"))


def stub_cancel(request):
    if not getattr(django_settings, "PAYMENTS_STUB", False):
        return HttpResponseNotFound("Payments stub is disabled")
    p = request.GET
    mark_cancelled(p.get("payment_id", ""))
    return HttpResponseRedirect(_append_query(p.get("return_url", "/"), "payment", "cancel"))
