from django.urls import path
from .views import PaymentHistoryView, YookassaWebhookView

urlpatterns = [
    path("history/", PaymentHistoryView.as_view(), name="payment-history"),
    path("webhook/yookassa/", YookassaWebhookView.as_view(), name="payment-webhook-yookassa"),
]
