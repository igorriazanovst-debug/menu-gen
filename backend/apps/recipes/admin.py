from django.contrib import admin
from .models import Recipe, RecipeAuthor


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "country", "is_custom", "is_published", "author", "created_at")
    list_filter = ("is_custom", "is_published", "country")
    search_fields = ("title", "legacy_id")
    raw_id_fields = ("author",)
    readonly_fields = ("legacy_id", "created_at", "updated_at")
    actions = ["publish", "unpublish"]

    @admin.action(description="Опубликовать выбранные")
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Снять с публикации")
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "applied_at", "approved_at")
    list_filter = ("status",)
    raw_id_fields = ("user",)
    actions = ["approve", "reject"]

    @admin.action(description="Одобрить заявки")
    def approve(self, request, queryset):
        from django.utils import timezone
        from apps.users.models import User
        now = timezone.now()
        for obj in queryset:
            obj.status = "approved"
            obj.approved_at = now
            obj.save(update_fields=["status", "approved_at"])
            User.objects.filter(id=obj.user_id).update(user_type="recipe_author")

    @admin.action(description="Отклонить заявки")
    def reject(self, request, queryset):
        queryset.update(status="rejected")
