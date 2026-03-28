from django.db import models

from apps.family.models import Family


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    default_unit = models.CharField(max_length=50, blank=True)
    calories_per_100g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    nutrition = models.JSONField(default=dict)
    barcode = models.CharField(max_length=64, null=True, blank=True, unique=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["barcode"]),
        ]

    def __str__(self):
        return self.name


class FridgeItem(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="fridge_items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    added_by_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fridge_items"
        indexes = [
            models.Index(fields=["family_id"]),
            models.Index(fields=["product_id"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["is_deleted"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.family})"
