from django import forms
from django.contrib import admin, messages
from django.shortcuts import render
from django.urls import path
from django.utils import timezone

from .models import MenuGenerationCounter, PromoCode, PromoRedemption, Subscription, SubscriptionPlan
from .promo import generate_unique_codes


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


@admin.register(MenuGenerationCounter)
class MenuGenerationCounterAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "period_start", "count", "updated_at")
    search_fields = ("family__name", "family__owner__email")
    raw_id_fields = ("family",)


class PromoBatchForm(forms.Form):
    """Форма пакетной генерации промокодов."""

    plan = forms.ModelChoiceField(queryset=SubscriptionPlan.objects.filter(is_active=True), label="Тариф")
    count = forms.IntegerField(min_value=1, max_value=2000, initial=1, label="Сколько кодов")
    max_redemptions = forms.IntegerField(min_value=1, initial=1, label="Активаций на код (1 — одноразовый)")
    duration_days = forms.IntegerField(min_value=1, required=False, label="Срок подписки, дней (пусто — период плана)")
    valid_until = forms.DateTimeField(required=False, label="Код действует до (пусто — без ограничения)")
    campaign = forms.CharField(max_length=100, required=False, label="Метка кампании")
    prefix = forms.CharField(max_length=12, required=False, label="Префикс кода (напр. NY26-)")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "plan",
        "duration_days",
        "redeemed_count",
        "max_redemptions",
        "is_active",
        "valid_until",
        "campaign",
        "created_at",
    )
    list_filter = ("is_active", "plan", "campaign")
    search_fields = ("code", "campaign")
    readonly_fields = ("redeemed_count", "created_by", "created_at")
    change_list_template = "admin/subscriptions/promocode/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("generate/", self.admin_site.admin_view(self.generate_view), name="promocode_generate"),
        ]
        return custom + urls

    def generate_view(self, request):
        generated = None
        if request.method == "POST":
            form = PromoBatchForm(request.POST)
            if form.is_valid():
                cd = form.cleaned_data
                codes = generate_unique_codes(cd["count"], prefix=cd.get("prefix") or "")
                objs = [
                    PromoCode(
                        code=c,
                        plan=cd["plan"],
                        duration_days=cd.get("duration_days"),
                        max_redemptions=cd["max_redemptions"],
                        valid_until=cd.get("valid_until"),
                        campaign=cd.get("campaign") or "",
                        is_active=True,
                        created_by=request.user if request.user.is_authenticated else None,
                    )
                    for c in codes
                ]
                PromoCode.objects.bulk_create(objs)
                generated = codes
                self.message_user(request, f"Сгенерировано кодов: {len(codes)}.", level=messages.SUCCESS)
        else:
            form = PromoBatchForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Генерация промокодов",
            "form": form,
            "generated": generated,
            "opts": self.model._meta,
            "now": timezone.now(),
        }
        return render(request, "admin/subscriptions/promocode/generate.html", context)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ("id", "promo", "family", "user", "subscription", "redeemed_at")
    search_fields = ("promo__code", "family__name", "user__email")
    raw_id_fields = ("promo", "family", "user", "subscription")
    readonly_fields = ("redeemed_at",)
