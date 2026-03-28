from django.contrib import admin

from .models import DocumentAccessLog, DocumentArchive, Recommendation, Specialist, SpecialistAssignment


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "specialist_type", "is_verified", "verified_at")
    list_filter = ("specialist_type", "is_verified")
    raw_id_fields = ("user",)
    actions = ["verify"]

    @admin.action(description="Верифицировать специалистов")
    def verify(self, request, queryset):
        from django.utils import timezone

        queryset.update(is_verified=True, verified_at=timezone.now())


@admin.register(SpecialistAssignment)
class SpecialistAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "specialist", "status", "assigned_at")
    list_filter = ("status",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "rec_type", "name", "is_active", "created_at")
    list_filter = ("rec_type", "is_active")


@admin.register(DocumentArchive)
class DocumentArchiveAdmin(admin.ModelAdmin):
    list_display = ("id", "specialist", "document_type", "retention_until", "uploaded_at")
    readonly_fields = ("encrypted_data", "encryption_key_id")

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "accessed_by", "access_reason", "accessed_at")
    readonly_fields = ("document", "accessed_by", "accessed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
