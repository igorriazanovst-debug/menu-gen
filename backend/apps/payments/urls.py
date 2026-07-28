from django.urls import path

from .views import PaymentHistoryView, YookassaWebhookView, stub_cancel, stub_checkout, stub_confirm

urlpatterns = [
    path("history/", PaymentHistoryView.as_view(), name="payment-history"),
    path("webhook/yookassa/", YookassaWebhookView.as_view(), name="payment-webhook-yookassa"),
    # MG_PAYSTUB: тестовая имитация оплаты (активна только при PAYMENTS_STUB)
    path("stub/checkout/", stub_checkout, name="payment-stub-checkout"),
    path("stub/confirm/", stub_confirm, name="payment-stub-confirm"),
    path("stub/cancel/", stub_cancel, name="payment-stub-cancel"),
]
