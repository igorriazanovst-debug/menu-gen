from django.contrib import admin
from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "price", "period", "max_family_members", "is_active", "sort_order")
    list_editable = ("sort_order", "is_active")
    ordering = ("sort_order",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "plan", "status", "started_at", "expires_at", "auto_renew")
    list_filter = ("status", "plan")
    search_fields = ("family__name", "family__owner__email")
    raw_id_fields = ("family",)
