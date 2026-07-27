from django.contrib import admin
from django.utils.html import format_html

from .models import LegalInfo


@admin.register(LegalInfo)
class LegalInfoAdmin(admin.ModelAdmin):
    readonly_fields = ("logo_preview", "updated_at")
    fieldsets = (
        ("Реквизиты ИП", {"fields": ("company_name", "inn", "ogrnip", "legal_address", "email", "phone")}),
        ("Банковские реквизиты", {"fields": ("bank_name", "bank_bik", "bank_account", "corr_account")}),
        ("Дополнительно", {"fields": ("requisites_extra",)}),
        ("Оферта", {"fields": ("offer_text",)}),
        ("Логотип", {"fields": ("logo", "logo_preview")}),
        (None, {"fields": ("updated_at",)}),
    )

    @admin.display(description="Превью логотипа")
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height:80px" />', obj.logo.url)
        return "— (на сайте показывается заглушка-помидор)"

    # Синглтон: одна запись, без добавления/удаления.
    def has_add_permission(self, request):
        return not LegalInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
