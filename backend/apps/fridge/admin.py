import os

from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .models import FridgeItem, Product


class ProductAdminForm(forms.ModelForm):
    # MG_OFFIMG: загрузка изображения файлом (как у рецептов) — при сохранении
    # кладётся в media и подставляется в image_url.
    upload_image = forms.ImageField(required=False, label="Загрузить изображение (файл)")

    class Meta:
        model = Product
        fields = "__all__"


class HasImageFilter(admin.SimpleListFilter):
    """MG_PRODOWN: фильтр «есть изображение / нет» — для точечного добавления фото."""

    title = "Изображение"
    parameter_name = "has_image"

    def lookups(self, request, model_admin):
        return (("yes", "С изображением"), ("no", "Без изображения"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(Q(image_url__isnull=True) | Q(image_url=""))
        if self.value() == "no":
            return queryset.filter(Q(image_url__isnull=True) | Q(image_url=""))
        return queryset


class ProductKindFilter(admin.SimpleListFilter):
    """Системный (owner is null) vs пользовательский продукт."""

    title = "Тип продукта"
    parameter_name = "kind"

    def lookups(self, request, model_admin):
        return (("system", "Системные"), ("user", "Пользовательские"))

    def queryset(self, request, queryset):
        if self.value() == "system":
            return queryset.filter(owner__isnull=True)
        if self.value() == "user":
            return queryset.filter(owner__isnull=False)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    # Продукты-кандидаты на замену блюда = все продукты в поиске (системные +
    # пользовательские). Для добавления фото удобны: превью, фильтр «без фото»,
    # inline-правка image_url в списке и загрузка файла на странице продукта.
    list_display = (
        "id",
        "name",
        "image_preview",
        "kind",
        "has_image",
        "image_url",
        "category",
        "calories_per_100g",
        "barcode",
    )
    list_editable = ("image_url",)
    list_display_links = ("name",)
    search_fields = ("name", "barcode", "owner__email", "owner__name")
    list_filter = (HasImageFilter, ProductKindFilter, "is_seed", "category")
    raw_id_fields = ("owner", "category_fk")
    readonly_fields = ("image_preview",)
    actions = ("fetch_images_fill", "fetch_images_overwrite", "clear_images")

    def _maybe_delete_local_file(self, image_url):
        """Удалить локальный файл, если URL указывает на наш media/product_images."""
        if not image_url or "/media/product_images/" not in image_url:
            return
        try:
            rel = image_url.split("/media/", 1)[1]  # product_images/xxx.jpg
            path = os.path.join(settings.MEDIA_ROOT, rel)
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    def save_model(self, request, obj, form, change):
        # MG_OFFIMG: если загрузили файл — сохраняем его в media и ставим в image_url.
        upload = form.cleaned_data.get("upload_image")
        if upload:
            from .services import save_uploaded_image_to_media

            url = save_uploaded_image_to_media(upload)
            if url:
                obj.image_url = url
        super().save_model(request, obj, form, change)

    @admin.action(description="Удалить фото у выбранных продуктов")
    def clear_images(self, request, queryset):
        cleared = 0
        for p in queryset:
            if p.image_url:
                self._maybe_delete_local_file(p.image_url)
                p.image_url = None
                p.save(update_fields=["image_url"])
                cleared += 1
        self.message_user(request, f"Фото удалено у {cleared} продуктов.")

    def _fetch_images(self, request, queryset, overwrite):
        from .services import fetch_product_image_url

        updated = missed = skipped = 0
        for p in queryset:
            if p.image_url and not overwrite:
                skipped += 1
                continue
            img = fetch_product_image_url(p.name)
            if img:
                p.image_url = img
                p.save(update_fields=["image_url"])
                updated += 1
            else:
                missed += 1
        self.message_user(
            request,
            f"Openverse: обновлено {updated}, без результата {missed}, пропущено (уже с фото) {skipped}.",
        )

    @admin.action(description="Загрузить фото (Openverse) — только без фото")
    def fetch_images_fill(self, request, queryset):
        self._fetch_images(request, queryset, overwrite=False)

    @admin.action(description="Загрузить фото (Openverse) — перезаписать")
    def fetch_images_overwrite(self, request, queryset):
        self._fetch_images(request, queryset, overwrite=True)

    @admin.display(description="Тип")
    def kind(self, obj):
        return "системный" if obj.owner_id is None else f"польз. #{obj.owner_id}"

    @admin.display(boolean=True, description="Фото")
    def has_image(self, obj):
        return bool(obj.image_url)

    @admin.display(description="Превью")
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:6px" />',
                obj.image_url,
            )
        return "—"


@admin.register(FridgeItem)
class FridgeItemAdmin(admin.ModelAdmin):
    list_display = ("id", "family", "name", "quantity", "unit", "expiry_date", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "family__name")
    raw_id_fields = ("family", "product")
