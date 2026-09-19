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
    # MG_SHELFLIFE: сколько продукт этой категории живёт ПОСЛЕ ПОКУПКИ.
    #
    # Именно после покупки, а не от даты производства: производства мы не знаем,
    # знаем только день, когда товар попал в дом. Хранить «срок по ГОСТу» и
    # вычитать из него поправку на «сколько уже пролежал» — значит гадать дважды;
    # поправка вдобавок не может быть одинаковой (у молока 8 дней и у крупы год).
    # Пусто — срок не подставляется.
    shelf_life_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Сколько хранится после покупки, дней. Пусто — не подставлять."
    )
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
    # MG_PRODOWN: кто добавил продукт. На видимость больше не влияет — только
    # авторство (видно в админке, помогает разобраться, откуда взялась запись).
    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
        help_text="Кто добавил. Видимость определяет «Семья-владелец».",
    )
    # MG_PRODFAMILY: чей это продукт. NULL → общий каталог: он один на всех,
    # правится только админами и не растёт от пользовательского ввода. Задана
    # семья → продукт этой семьи, виден только её участникам.
    #
    # Владелец именно семья, а не пользователь: список покупок ведут вдвоём, и
    # товар, добавленный одним, должен быть виден второму. Фильтр — один на все
    # точки входа, см. apps/fridge/visibility.py.
    owner_family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
        help_text="NULL = общий каталог (виден всем); иначе — продукт этой семьи.",
    )

    class Source(models.TextChoices):
        MANUAL = "manual", "Заведён вручную"
        AUTO = "auto", "Из ингредиентов рецепта"
        IMPORT = "import", "Импорт"
        OFF = "off", "Скан: OpenFoodFacts"
        AI = "ai", "Скан: догадка ИИ"
        # MG_BARCODEDB: выгрузка товаров розничной сети со штрих-кодами.
        # Это конкретные SKU («Соус Tabasco красный перечный, 350мл»), а не
        # справочные продукты: они нужны, чтобы опознать сканируемую упаковку,
        # но в списках выбора утопили бы каталог — см. visibility.py.
        RETAIL = "retail", "Каталог сети (штрих-коды)"
        # MG_BARCODEOFF: выгрузка OpenFoodFacts. Отдельно от RETAIL, потому что
        # это разное по надёжности: каталог сети — её собственный артикул с
        # аккуратным названием, OFF — общая база, куда названия вносят люди
        # («cola», «0157», транслит). Опознать упаковку хватает и такого, но при
        # совпадении кода название сети должно побеждать — см. TRUST в
        # import_barcode_catalog.
        OFFBULK = "off_bulk", "Справочник OpenFoodFacts"

    # MG_T04C: provenance — manual catalog vs auto-created from recipe ingredients.
    # MG_SCANSRC: плюс происхождение сканов. Отличать их важно: запись из
    # OpenFoodFacts проверяема (штрих-код глобальный, база открытая), а догадка
    # модели по коду — нет, и в общий каталог ей нельзя (см. visibility.py).
    source = models.CharField(
        max_length=16, default=Source.MANUAL, choices=Source.choices, help_text="Откуда взялась запись."
    )
    # MG_RUBRIC001: rubricator metadata.
    subcategory = models.CharField(max_length=128, blank=True)
    popularity = models.CharField(max_length=16, blank=True, help_text="часто|средне|редко")
    # MG_SHELFLIFE: срок хранения конкретного продукта, если он не как у всей
    # категории (ультрапастеризованное молоко живёт полгода, обычное — неделю).
    # Пусто — берётся из категории.
    shelf_life_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Хранится после покупки, дней. Пусто — как у категории."
    )
    # MG_NOBUY: есть ингредиенты, которые в рецептах есть, а в магазине не
    # покупают: вода во всех видах, лёд. В списке они занимают строку и сбивают
    # счёт — «Вода — 2.5 л» человек вычёркивает каждый раз заново. Признак
    # ставится редактором у конкретного товара, а не зашит списком имён в коде:
    # что не покупается, зависит от хозяйства, и правило тут не наше.
    skip_in_shopping = models.BooleanField(
        default=False, help_text="Не добавлять в список покупок (вода, лёд и прочее, что не покупают)."
    )
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
            models.Index(fields=["owner"]),  # MG_PRODOWN
            models.Index(fields=["owner_family"]),  # MG_PRODFAMILY
        ]

    def __str__(self):
        return self.name

    # MG_PRODDISH: КБЖУ порции продукта (в граммах) из значений на 100 г.
    def nutrition_for_grams(self, grams):
        factor = (float(grams) if grams else 0) / 100.0
        n = self.nutrition if isinstance(self.nutrition, dict) else {}

        def _scaled(*keys):
            for k in keys:
                v = n.get(k)
                if v is not None:
                    try:
                        return round(float(v) * factor, 1)
                    except (TypeError, ValueError):
                        pass
            return None

        kcal = None
        if self.calories_per_100g is not None:
            try:
                kcal = round(float(self.calories_per_100g) * factor)
            except (TypeError, ValueError):
                kcal = None
        if kcal is None:
            c = _scaled("calories", "kcal")
            kcal = round(c) if c is not None else None
        return {
            "calories": kcal,
            "proteins": _scaled("proteins", "protein"),
            "fats": _scaled("fats", "fat"),
            "carbs": _scaled("carbs", "carb"),
        }


class FamilyBarcode(models.Model):
    """MG_FAMBARCODE: «этот код у нас — вот это». Память семьи о своих товарах.

    Справочник сети покрывает её ассортимент, OpenFoodFacts — что попало в
    открытую базу. Всё остальное человек вбивал руками каждый раз заново: код
    нигде не оставался, и та же упаковка завтра снова «не найдена».

    Отдельная таблица, а не продукт со штрих-кодом: `Product.barcode` уникален
    на всю базу, и запись одной семьи заняла бы код у всех остальных. Здесь же
    у каждой семьи своя строка на один и тот же код — а «Сметана 20%» у соседей
    вполне может быть другой марки.

    Хранится ровно то, что подставляется в форму добавления: название, единица
    и категория. КБЖУ нет намеренно: в холодильник его не вводят, и выдумывать
    место для чисел, которых никто не вносил, незачем.
    """

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="barcodes")
    # Канонический вид (13 цифр) — см. apps/fridge/barcodes.py. Сканеры отдают
    # один и тот же код по-разному, поэтому сравниваем приведённым.
    barcode = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    category_fk = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="family_barcodes"
    )
    created_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="family_barcodes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "family_barcodes"
        constraints = [
            models.UniqueConstraint(fields=["family", "barcode"], name="uniq_family_barcode"),
        ]
        indexes = [models.Index(fields=["barcode"])]

    def __str__(self):
        return f"{self.barcode} → {self.name}"


class FridgeItem(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="fridge_items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    # MG_T07: per-item category override; does NOT mutate the shared Product.
    category_fk = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fridge_items",
    )
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    added_by_id = models.BigIntegerField(null=True, blank=True)
    # MG_SHOP2FRIDGE: link back to the purchased shopping item this fridge item
    # came from. Lets un-checking that item remove exactly what was added.
    source_shopping_item = models.ForeignKey(
        "shopping.ShoppingListItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fridge_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fridge_items"
        indexes = [
            models.Index(fields=["family_id"]),
            models.Index(fields=["product_id"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["is_deleted"]),
            # MG_SHOP2FRIDGE
            models.Index(fields=["source_shopping_item"], name="fridge_item_src_shop_idx"),
        ]

    @property
    def effective_category(self):  # MG_T07
        if self.category_fk_id:
            return self.category_fk
        if self.product_id and self.product and self.product.category_fk_id:
            return self.product.category_fk
        return None

    def __str__(self):
        return f"{self.name} ({self.family})"


class ProductAlias(models.Model):
    """MG_PRODALIAS — synonym/spelling variant -> canonical Product."""

    alias_norm = models.CharField(max_length=255, unique=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="aliases")
    source = models.CharField(max_length=16, default="manual", help_text="manual|auto")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_aliases"

    def __str__(self):
        return f"{self.alias_norm} -> {self.product_id}"


class ProductUnitWeight(models.Model):
    """MG_UNITNORM: сколько граммов в одной «штуке», «упаковке», «литре» товара.

    Холодильник хранит то, что человек принёс из магазина: яйца в штуках, творог
    в упаковках, молоко в литрах. Рецепты и список покупок считают в граммах.
    Пока перевода не было, эти две правды не встречались: «Яйца куриные 50 г»
    для блюда не находили в холодильнике «яйца 30 шт», хотя товар определялся
    верно. Списание это показало, а список покупок вёл себя так же — молча, и
    человек просто получал в списке то, что у него лежит.

    Перевод один на оба конца: «одна единица U товара P весит N граммов».
    Поэтому таблица не про штуки, а про любую единицу — `шт`, `упаковка`,
    `банка`, `л` (для жидкого это заодно плотность), `пучок`, `ломтик`.

    Данные заводятся по товару и только явно. Угадывать «в среднем по
    категории» здесь нельзя: ошибка в весе не видна никому и тихо уносит из
    холодильника не то количество. Чего нет — то и не сходится, как раньше:
    честная нехватка лучше выдуманного остатка.
    """

    class Source(models.TextChoices):
        SEED = "seed", "Справочник"
        MANUAL = "manual", "Указано человеком"
        AI = "ai", "Оценка модели"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_weights")
    # Единица в нормализованном виде (см. _mg_norm_unit): «шт», а не «шт.».
    unit = models.CharField(max_length=50)
    grams = models.DecimalField(max_digits=10, decimal_places=2, help_text="Сколько граммов в одной такой единице")
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_unit_weights"
        constraints = [
            models.UniqueConstraint(fields=["product", "unit"], name="uniq_product_unit_weight"),
        ]
        indexes = [models.Index(fields=["unit"])]

    def __str__(self):
        return f"{self.product_id}: 1 {self.unit} = {self.grams} г"


class FridgeWriteOff(models.Model):
    """MG_WRITEOFF: событие списания продуктов из холодильника.

    Списание — это не просто «минус к количеству». Без записи о том, что и
    откуда ушло, нельзя ни отменить ошибочное нажатие, ни ответить человеку,
    почему у него пропал фарш. Поэтому событие хранится целиком, а строки
    (FridgeWriteOffLine) помнят каждую затронутую позицию.

    Событие привязано к БЛЮДУ, а не к отметке человека. Пункт меню принадлежит
    участнику семьи: одно блюдо на троих — это три пункта, и «съел» отметят
    трое. Списаться при этом должно один раз, поэтому ключ события — меню,
    день, приём и рецепт, и он уникален.
    """

    class Reason(models.TextChoices):
        COOKED = "cooked", "Приготовлено по меню"
        MANUAL = "manual", "Списано вручную"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="fridge_write_offs")
    reason = models.CharField(max_length=16, choices=Reason.choices, default=Reason.COOKED)

    # Ключ блюда. Пусто — ручное списание, оно ни с чем не сверяется.
    menu = models.ForeignKey("menu.Menu", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    day_offset = models.PositiveSmallIntegerField(null=True, blank=True)
    meal_slot = models.CharField(max_length=20, blank=True)

    created_by_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fridge_write_offs"
        indexes = [models.Index(fields=["family", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["family", "menu", "day_offset", "meal_slot", "recipe"],
                condition=models.Q(menu__isnull=False),
                name="uniq_fridge_writeoff_per_dish",
            )
        ]

    def __str__(self):
        return f"{self.get_reason_display()} #{self.pk} ({self.family})"


class FridgeWriteOffLine(models.Model):
    """Одна строка списания: что и сколько ушло, и чего не хватило.

    Строка без `fridge_item` — это нехватка: продукт нужен был, а в холодильнике
    его не нашлось. Человек решает её сам («докупил»), и мы не выдумываем за
    него остатки.

    Количество хранится в единице ТОЙ позиции, из которой списали, а нехватка —
    в единице потребности: иначе отмена вернула бы в холодильник не то число.
    """

    write_off = models.ForeignKey(FridgeWriteOff, on_delete=models.CASCADE, related_name="lines")
    fridge_item = models.ForeignKey(FridgeItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    name = models.CharField(max_length=255)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    shortfall = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shortfall_unit = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "fridge_write_off_lines"
        indexes = [models.Index(fields=["write_off"])]

    def __str__(self):
        return f"{self.name}: -{self.quantity} {self.unit}"
