from django.contrib import admin

from .models import FridgeItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "default_unit", "calories_per_100g", "barcode", "is_seed", "owner")
    search_fields = ("name", "barcode", "owner__email", "owner__name")
    list_filter = ("is_seed", "category")
    raw_id_fields = ("owner", "category_fk")


@admin.register(FridgeItem)
class FridgeItemAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "name", "quantity", "unit", "expiry_date", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "family__name")
    raw_id_fields = ("family", "product")
