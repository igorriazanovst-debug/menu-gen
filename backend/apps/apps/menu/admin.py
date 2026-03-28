from django.contrib import admin
from .models import Menu, MenuItem, ShoppingItem, ShoppingList


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    raw_id_fields = ("recipe", "member")


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "start_date", "end_date", "status", "generated_at")
    list_filter = ("status",)
    raw_id_fields = ("family",)
    inlines = [MenuItemInline]


class ShoppingItemInline(admin.TabularInline):
    model = ShoppingItem
    extra = 0


@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "menu", "created_at")
    raw_id_fields = ("family", "menu")
    inlines = [ShoppingItemInline]
