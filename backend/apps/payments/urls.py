from django.urls import path

from .views import (
    PaymentHistoryView,
    PaymentStatusView,
    YookassaWebhookView,
    stub_cancel,
    stub_checkout,
    stub_confirm,
)

urlpatterns = [
    path("history/", PaymentHistoryView.as_view(), name="payment-history"),
    # MG_PAYRELIABLE: «я вернулся с оплаты, что там?» — не ждём уведомления
    path("<str:payment_id>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("webhook/yookassa/", YookassaWebhookView.as_view(), name="payment-webhook-yookassa"),
    # MG_PAYSTUB: тестовая имитация оплаты (активна только при PAYMENTS_STUB)
    path("stub/checkout/", stub_checkout, name="payment-stub-checkout"),
    path("stub/confirm/", stub_confirm, name="payment-stub-confirm"),
    path("stub/cancel/", stub_cancel, name="payment-stub-cancel"),
]
