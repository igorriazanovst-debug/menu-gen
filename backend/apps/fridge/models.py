from django.db import models

from apps.family.models import Family


class ProductCategory(models.Model):
    """
    Normalized product category (dairy, meat, vegetables, ...).
    Used to group fridge view by groups and to render coloured zones.
    """

    slug = models.SlugField(max_length=64, unique=True)
    name_ru = models.CharField(max_length=128)
    name_en = models.CharField(max_length=128, blank=True)
    icon = models.CharField(max_length=16, blank=True, help_text="Emoji or short symbol")
    color = models.CharField(max_length=16, blank=True, help_text="Hex color, e.g. #FFE082")
    sort_order = models.PositiveIntegerField(default=100)
    # MG_RUBRIC001: store department (магазинный отдел) for print routing.
    department = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product_categories"
        ordering = ["sort_order", "name_ru"]
        indexes = [models.Index(fields=["slug"])]

    def __str__(self):
        return self.name_ru


class Product(models.Model):
    name = models.CharField(max_length=255)
    # Legacy free-form category text (kept for backward compat / OFF imports).
    category = models.CharField(max_length=100, blank=True)
    # New normalized FK.
    category_fk = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        db_column="category_id",
    )
    default_unit = models.CharField(max_length=50, blank=True)
    calories_per_100g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    nutrition = models.JSONField(default=dict)
    barcode = models.CharField(max_length=64, null=True, blank=True, unique=True)
    image_url = models.URLField(max_length=1024, null=True, blank=True)
    is_seed = models.BooleanField(default=False, help_text="True for built-in basic products")
    # MG_RUBRIC001: rubricator metadata.
    subcategory = models.CharField(max_length=128, blank=True)
    popularity = models.CharField(max_length=16, blank=True, help_text="часто|средне|редко")
    # MG_RUBRIC006: last known price per unit (auto-updated on purchase).
    last_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_price_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["category_fk"]),
            models.Index(fields=["is_seed"]),
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
