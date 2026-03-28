from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("id", "email", "phone", "name", "user_type", "is_active", "created_at")
    list_filter = ("user_type", "is_active")
    search_fields = ("email", "phone", "name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "phone", "vk_id", "password")}),
        ("Личные данные", {"fields": ("name", "avatar_url", "allergies", "disliked_products")}),
        (
            "Роли и доступ",
            {"fields": ("user_type", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),)
