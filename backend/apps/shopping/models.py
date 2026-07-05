# MG_SHOP001_models — shopping domain (lists, items, access, history)
from django.db import models

from apps.family.models import Family
from apps.menu.models import Menu
from apps.users.models import User


class ShoppingList(models.Model):
    class Source(models.TextChoices):
        EMPTY = "empty", "Пустой"
        MENU = "menu", "Из меню"
        FRIDGE = "fridge", "Меню минус холодильник"
        AI_TEXT = "ai_text", "Импорт из текста (ИИ)"
        CSV = "csv", "Импорт из CSV"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="shopping_v2_lists")
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_shopping_lists",
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.EMPTY)
    menu = models.ForeignKey(
        Menu,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_v2_lists",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shopping_v2_lists"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["family_id", "is_archived"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.family_id})"


class ShoppingListItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    # MG_RUBRIC003: renamed from product_id to free the attribute for the FK below.
    legacy_product_id = models.BigIntegerField(null=True, blank=True, db_column="product_id")
    # MG_RUBRIC001: strong FK links to the product rubricator.
    product = models.ForeignKey(
        "fridge.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_items",
        db_column="product_fk_id",
    )
    category_fk = models.ForeignKey(
        "fridge.ProductCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_items",
        db_column="category_id",
    )
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_purchased = models.BooleanField(default=False)
    purchased_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchased_shopping_items",
    )
    purchased_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    # MG_RUBRIC006: per-unit price snapshot for this list.
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # MG_SHOPNOTE: свободный комментарий к товару.
    note = models.TextField(blank=True, default="")
    # MG_SHOPIMG: изображение товара — загруженный файл (камера/буфер) и/или URL.
    image = models.ImageField(upload_to="shopping_items/", null=True, blank=True)
    image_url = models.URLField(max_length=1024, blank=True, default="")

    class Meta:
        db_table = "shopping_v2_items"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["shopping_list_id", "is_purchased"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.name


class ShoppingListAccess(models.Model):
    """Доступ к списку: член семьи или любой пользователь по email."""

    # MG_SHAREACCEPT: lifecycle of an external share invitation.
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает принятия"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"

    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="accesses")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shopping_list_accesses")
    can_read = models.BooleanField(default=True)
    can_toggle = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    granted_at = models.DateTimeField(auto_now_add=True)
    # MG_SHAREACCEPT: ACCEPTED default backfills existing rows; new external
    # grants are set to PENDING explicitly in the view.
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACCEPTED)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shopping_v2_access"
        unique_together = [("shopping_list", "user")]
        indexes = [
            models.Index(fields=["user_id"]),
        ]

    def __str__(self):
        return f"{self.user_id} -> list {self.shopping_list_id}"


class PurchaseHistoryEntry(models.Model):
    """Лог отдельных купленных позиций."""

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="purchase_history")
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=100, blank=True)
    purchased_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_history_entries",
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    source_list_id = models.BigIntegerField(null=True, blank=True)
    # MG_RUBRIC006: price at purchase time.
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "shopping_v2_history"
        ordering = ["-purchased_at"]
        indexes = [
            models.Index(fields=["family_id", "purchased_at"]),
        ]

    def __str__(self):
        return f"{self.name} @ {self.purchased_at}"
