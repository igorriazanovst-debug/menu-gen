from django.contrib import admin

from .models import FridgeItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "default_unit", "calories_per_100g", "barcode")
    search_fields = ("name", "barcode")
    list_filter = ("category",)


@admin.register(FridgeItem)
class FridgeItemAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "name", "quantity", "unit", "expiry_date", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "family__name")
    raw_id_fields = ("family", "product")
