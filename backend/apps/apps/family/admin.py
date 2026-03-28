from django.contrib import admin
from .models import Family, FamilyMember


class FamilyMemberInline(admin.TabularInline):
    model = FamilyMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "created_at")
    search_fields = ("name", "owner__email")
    raw_id_fields = ("owner",)
    inlines = [FamilyMemberInline]
