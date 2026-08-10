# MG_SHOP001_admin
from django.contrib import admin

from apps.common.search import AdminSearchMixin  # MG_YOSEARCH/MG_MORPHSEARCH

from .models import PurchaseHistoryEntry, ShoppingList, ShoppingListAccess, ShoppingListItem


class ShoppingListItemInline(admin.TabularInline):
    model = ShoppingListItem
    extra = 0


class ShoppingListAccessInline(admin.TabularInline):
    model = ShoppingListAccess
    extra = 0


@admin.register(ShoppingList)
class ShoppingListAdmin(AdminSearchMixin, admin.ModelAdmin):
    list_display = ("id", "name", "family", "source", "is_archived", "created_at")
    list_filter = ("source", "is_archived")
    search_fields = ("name",)
    inlines = [ShoppingListItemInline, ShoppingListAccessInline]


@admin.register(PurchaseHistoryEntry)
class PurchaseHistoryEntryAdmin(AdminSearchMixin, admin.ModelAdmin):
    list_display = ("id", "name", "family", "quantity", "unit", "purchased_at")
    list_filter = ("category",)
    search_fields = ("name",)
