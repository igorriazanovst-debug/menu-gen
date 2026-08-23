from django.contrib import admin
from django.utils.html import format_html

from .models import AndroidBuild, LegalInfo


@admin.register(LegalInfo)
class LegalInfoAdmin(admin.ModelAdmin):
    readonly_fields = ("logo_preview", "updated_at")
    fieldsets = (
        ("Реквизиты ИП", {"fields": ("company_name", "inn", "ogrnip", "legal_address", "email", "phone")}),
        ("Банковские реквизиты", {"fields": ("bank_name", "bank_bik", "bank_account", "corr_account")}),
        ("Дополнительно", {"fields": ("requisites_extra",)}),
        ("Оферта", {"fields": ("offer_text",)}),
        (
            "Политика обработки персональных данных",  # MG_PRIVACY
            {
                "fields": ("privacy_text",),
                "description": (
                    "Оставьте пустым — на сайте покажется типовой текст (152-ФЗ) "
                    "с подстановкой реквизитов выше. Рекомендуется согласовать "
                    "формулировки с юристом перед публикацией."
                ),
            },
        ),
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


@admin.register(AndroidBuild)
class AndroidBuildAdmin(admin.ModelAdmin):
    """MG_APKSITE: выложенные сборки.

    Файл сюда не загружают — он приезжает командой `publish_apk` (apk весит
    десятки мегабайт и упёрся бы в ограничение nginx). Здесь правят описание
    и снимают сборку с сайта галочкой.
    """

    list_display = ("version_name", "version_code", "size_mb", "is_published", "created_at")
    list_editable = ("is_published",)
    list_display_links = ("version_name",)
    readonly_fields = ("file", "size_bytes", "sha256", "created_at")
    search_fields = ("version_name", "sha256")

    @admin.display(description="Размер")
    def size_mb(self, obj):
        return f"{obj.size_bytes / (1024 * 1024):.1f} МБ" if obj.size_bytes else "—"
