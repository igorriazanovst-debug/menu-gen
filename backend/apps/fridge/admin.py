import os

from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from apps.common.search import AdminSearchMixin  # MG_YOSEARCH/MG_MORPHSEARCH

from .models import FridgeItem, Product, ProductCategory, ProductUnitWeight


class ProductAdminForm(forms.ModelForm):
    """MG_ADMINFORM: форма, в которой видно, что заполнять.

    Завести товар руками было нельзя: два десятка полей подряд без подсказок,
    рубрика — поле для ввода номера (raw_id), и половина полей вообще не про
    ручное заведение, а про импорт штрих-кодов. На проде это кончилось тем, что
    «Окорочок куриный» и «Колбаски охотничьи» пришлось заводить скриптом.

    Поэтому: рубрика — выпадающий список и обязательна (товар без рубрики
    уезжает в «Прочее», и мы это уже разгребали), старое текстовое поле
    категории из формы убрано — его заполняет импорт, а руками оно только
    путает, — остальное разложено по разделам, редкое свёрнуто.
    """

    # MG_OFFIMG: загрузка изображения файлом (как у рецептов) — при сохранении
    # кладётся в media и подставляется в image_url.
    upload_image = forms.ImageField(
        required=False,
        label="Загрузить изображение (файл)",
        help_text="Файл ляжет в media, ссылка подставится сама.",
    )

    class Meta:
        model = Product
        exclude = ("category",)  # legacy: текстовая категория, её заполняет импорт OFF
        help_texts = {
            "name": "Как человек напишет это в списке покупок: «Окорочок куриный», «Сыр моцарелла».",
            "default_unit": "г, мл, шт. Пусто — единицу подставит рецепт.",
            "nutrition": 'На 100 г, ключи: {"proteins": 0, "fats": 0, "carbs": 0}. Пусто — не показываем.',
            "barcode": "Только для сканера. Руками обычно не нужен.",
            "owner_family": "Пусто — общий каталог, виден всем. Задана семья — только её участникам.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get("category_fk")
        if field is not None:
            field.queryset = ProductCategory.objects.filter(is_active=True).order_by("sort_order", "name_ru")
            field.label = "Рубрика"
            field.required = True
            field.help_text = "Раздел в списке покупок. Без неё товар попадёт в «Прочее»."

        # MG_ADMINKBJU: КБЖУ хранится с default=dict, но в форме оказывалось
        # обязательным — Django считает пустой словарь пустым значением. Из-за
        # этого товар не сохранялся, пока не откроешь свёрнутый раздел и не
        # впишешь туда JSON, а сообщение об ошибке пряталось там же.
        nutrition = self.fields.get("nutrition")
        if nutrition is not None:
            nutrition.required = False

    def clean_nutrition(self):
        return self.cleaned_data.get("nutrition") or {}


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
    """MG_PRODFAMILY: общий каталог (owner_family is null) vs продукт семьи."""

    title = "Тип продукта"
    parameter_name = "kind"

    def lookups(self, request, model_admin):
        return (("system", "Каталог (общие)"), ("user", "Продукты семей"))

    def queryset(self, request, queryset):
        if self.value() == "system":
            return queryset.filter(owner_family__isnull=True)
        if self.value() == "user":
            return queryset.filter(owner_family__isnull=False)
        return queryset


# MG_SHELFLIFE: справочник сроков хранения правится здесь.
#
# Числа — «сколько живёт ПОСЛЕ ПОКУПКИ», а не срок с этикетки: дату
# производства мы не знаем, поэтому поправка на пролежавшее уже зашита в само
# число. Пусто — срок не подставляется (для бытовой химии и корма так и надо).
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "slug", "department", "shelf_life_days", "sort_order", "is_active")
    list_editable = ("shelf_life_days", "sort_order", "is_active")
    list_display_links = ("name_ru",)
    search_fields = ("name_ru", "slug", "department")
    list_filter = ("is_active",)


class ProductUnitWeightInline(admin.TabularInline):
    """MG_UNITNORM: вес единицы товара — здесь, а не отдельным разделом.

    Заполняется редко и только для тех товаров, что лежат в холодильнике не в
    граммах: яйца в штуках, творог в упаковках, молоко в литрах. Без этой
    строки такой товар не сходится с рецептом и уходит в «не хватило», сколько
    бы его дома ни лежало.

    MG_FAMWEIGHT: пустая семья — общий вес, он один на всех. Заданная — вес
    этой семьи, и он перекрывает общий. Здесь видно оба уровня сразу, иначе
    непонятно, почему у одних считается так, а у других иначе.
    """

    model = ProductUnitWeight
    extra = 0
    fields = ("unit", "grams", "source", "family")
    autocomplete_fields = ("family",)
    verbose_name = "вес единицы"
    verbose_name_plural = "Вес единицы (шт, упаковка, л)"


@admin.register(Product)
class ProductAdmin(AdminSearchMixin, admin.ModelAdmin):
    form = ProductAdminForm
    inlines = [ProductUnitWeightInline]
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
        "source",  # MG_SCANSRC: видно, откуда запись — скан, рецепт или руки
        "skip_in_shopping",  # MG_NOBUY: вода и прочее, что не покупают
        "shelf_life_days",  # MG_SHELFLIFE
        "calories_per_100g",
        "barcode",
    )
    list_editable = ("image_url", "skip_in_shopping")
    list_display_links = ("name",)
    search_fields = ("name", "barcode", "owner__email", "owner__name", "owner_family__name")
    list_filter = (HasImageFilter, ProductKindFilter, "is_seed", "source", "skip_in_shopping", "category")
    autocomplete_fields = ("owner", "owner_family")
    readonly_fields = ("image_preview",)
    # Порядок разделов — по частоте: сверху то, что заполняют всегда, ниже то,
    # что заполняют раз в год, и оно свёрнуто.
    fieldsets = (
        (
            "Главное",
            {
                "fields": ("name", "category_fk", "default_unit", "skip_in_shopping"),
                "description": "Этого хватает, чтобы завести товар. Остальные разделы можно не открывать.",
            },
        ),
        (
            "Изображение",
            {"fields": ("image_preview", "upload_image", "image_url"), "classes": ("collapse",)},
        ),
        (
            "Пищевая ценность",
            {
                "fields": ("calories_per_100g", "nutrition"),
                "classes": ("collapse",),
                "description": "На список покупок не влияет — только на подсчёт калорий в дневнике.",
            },
        ),
        (
            "Происхождение и видимость",
            {
                "fields": ("source", "is_seed", "barcode", "owner", "owner_family"),
                "classes": ("collapse",),
                "description": "Заполняется импортом и сканером. Для товара, заведённого руками, менять нечего.",
            },
        ),
        (
            "Дополнительно",
            {
                "fields": ("subcategory", "popularity", "shelf_life_days", "last_price", "last_price_at"),
                "classes": ("collapse",),
                "description": "Срок хранения пуст — берётся у рубрики. Цену проставляет покупка.",
            },
        ),
    )
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
        # MG_PRODFAMILY: видимость определяет семья-владелец, не автор.
        if obj.owner_family_id is None:
            return "каталог"
        return f"семья #{obj.owner_family_id}"

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
class FridgeItemAdmin(AdminSearchMixin, admin.ModelAdmin):
    list_display = ("id", "family", "name", "quantity", "unit", "expiry_date", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "family__name")
    autocomplete_fields = ("family",)
    raw_id_fields = ("product",)
