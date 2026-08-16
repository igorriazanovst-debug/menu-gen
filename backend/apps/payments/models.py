from django.db import models

from apps.family.models import Family


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SUCCEEDED = "succeeded", "Успешно"
        CANCELLED = "cancelled", "Отменён"
        REFUNDED = "refunded", "Возврат"

    subscription = models.ForeignKey(
        "subscriptions.Subscription", on_delete=models.SET_NULL, null=True, related_name="payments"
    )
    # MG_PAYRELIABLE: что именно куплено. Раньше платёж не знал ни тарифа, ни
    # периода — сверить оплаченное было не с чем, а строка появлялась только
    # после успеха, поэтому «ожидает оплаты» показать было нечем.
    offer = models.ForeignKey(
        "subscriptions.PlanOffer", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="RUB")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # Идентификатор платежа у провайдера. Уникален: по нему идёт защита от
    # повторной активации — ЮKassa повторяет уведомление, пока не получит 200.
    payment_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    provider = models.CharField(max_length=50, default="yookassa")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=["subscription_id"]),
            models.Index(fields=["family_id", "status"]),
            models.Index(fields=["payment_id"]),
        ]

    def __str__(self):
        return f"Payment({self.family}, {self.amount} {self.currency}, {self.status})"
