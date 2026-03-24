from django.db import models
from apps.users.models import User


class SubscriptionPlan(models.Model):
    class Period(models.TextChoices):
        MONTH = "month", "Месяц"
        YEAR = "year", "Год"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.MONTH)
    features = models.JSONField(default=dict)
    max_family_members = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "subscription_plans"
        indexes = [models.Index(fields=["code"]), models.Index(fields=["is_active"])]

    def __str__(self):
        return f"{self.name} ({self.price} ₽/{self.period})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        CANCELLED = "cancelled", "Отменена"
        EXPIRED = "expired", "Истекла"
        TRIAL = "trial", "Пробный период"

    family = models.ForeignKey("family.Family", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [
            models.Index(fields=["family_id", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.family} — {self.plan.code} ({self.status})"
