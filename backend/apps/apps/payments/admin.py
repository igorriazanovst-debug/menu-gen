from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "amount", "currency", "status", "provider", "paid_at", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("family__name", "payment_id")
    raw_id_fields = ("family", "subscription")
    readonly_fields = ("payment_id", "created_at")
