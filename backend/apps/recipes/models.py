from django.contrib.postgres.indexes import GinIndex
from django.db import models

from apps.users.models import User


class Recipe(models.Model):
    legacy_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    cook_time = models.CharField(max_length=64, null=True, blank=True)
    servings = models.PositiveSmallIntegerField(null=True, blank=True)
    servings_normalized = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Нормализованное число порций (MG-104d-5)"
    )
    ingredients = models.JSONField(default=list)
    steps = models.JSONField(default=list)
    nutrition = models.JSONField(default=dict)
    categories = models.JSONField(default=list)
    # MG_ALLERGEN14: ключи аллергенов (ТР ТС 022/2011), найденных в рецепте.
    # Заполняется классификатором (apps.common.allergens) по ингредиентам+названию.
    allergens = models.JSONField(default=list, blank=True)
    # MG_IMGFIX: CharField (не URLField). URLField прогонял URLValidator в
    # Recipe.full_clean() (ModelForm._post_clean в админке) и отклонял
    # относительные пути `/media/...`. А сериализатор (_AbsoluteImageUrlMixin)
    # штатно поддерживает относительные пути и сам добавляет префикс backend.
    # Из-за валидации при сохранении рецепта в админке терялось изображение.
    image_url = models.CharField(null=True, blank=True, max_length=1024)
    video_url = models.CharField(null=True, blank=True, max_length=1024)
    source_url = models.CharField(null=True, blank=True, max_length=1024)
    country = models.CharField(max_length=100, null=True, blank=True)
    is_custom = models.BooleanField(default=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="recipes")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class FoodGroup(models.TextChoices):
        GRAIN = "grain", "Зерновые"
        PROTEIN = "protein", "Белки"
        VEGETABLE = "vegetable", "Овощи"
        FRUIT = "fruit", "Фрукты"
        DAIRY = "dairy", "Молочные"
        OIL = "oil", "Масла/жиры"
        OTHER = "other", "Прочее"

    class ProteinType(models.TextChoices):
        ANIMAL = "animal", "Животный"
        PLANT = "plant", "Растительный"
        MIXED = "mixed", "Смешанный"

    class GrainType(models.TextChoices):
        WHOLE = "whole", "Цельнозерновые"
        REFINED = "refined", "Рафинированные"

    class DishType(models.TextChoices):  # RB001_V_schema
        SOUP = "soup", "Первое (суп)"
        MAIN = "main", "Второе/горячее"
        SALAD = "salad", "Салат"
        SIDE = "side", "Гарнир"
        DESSERT = "dessert", "Десерт"
        DRINK = "drink", "Напиток/компот"
        BAKERY = "bakery", "Выпечка"
        SAUCE = "sauce", "Соус"
        SNACK = "snack", "Перекус"
        BREAKFAST_DISH = "breakfast_dish", "Завтрак-блюдо"

    class Source(models.TextChoices):  # RB001_V_schema
        OWN = "own", "Собственный"
        IMPORT = "import", "Импорт"
        USER = "user", "Пользовательский"
        PARSED = "parsed", "Спарсенный"

    class CookingMethod(models.TextChoices):  # MG_501_V_model
        BOILED = "boiled", "Варёное"
        BAKED = "baked", "Запечённое"
        FRIED = "fried", "Жареное"
        GRILLED = "grilled", "Гриль"
        RAW = "raw", "Сырое"
        STEWED = "stewed", "Тушёное"
        STEAMED = "steamed", "На пару"

    food_group = models.CharField(max_length=16, choices=FoodGroup.choices, null=True, blank=True)
    suitable_for = models.JSONField(default=list, blank=True)
    povar_raw = models.JSONField(blank=True, null=True)
    protein_type = models.CharField(max_length=8, choices=ProteinType.choices, null=True, blank=True)
    grain_type = models.CharField(max_length=8, choices=GrainType.choices, null=True, blank=True)
    is_fatty_fish = models.BooleanField(default=False)
    is_red_meat = models.BooleanField(default=False)
    kcal = models.DecimalField(
        max_digits=7, decimal_places=1, null=True, blank=True, help_text="Калорийность на 1 порцию, ккал (MG-104d-4)."
    )
    proteins = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, help_text="Белки на 1 порцию, г."
    )
    fats = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Жиры на 1 порцию, г.")
    carbs = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, help_text="Углеводы на 1 порцию, г."
    )
    cooking_method = models.CharField(
        max_length=16,
        choices=CookingMethod.choices,
        null=True,
        blank=True,
        help_text="Метод приготовления (MG-501).",
    )
    has_added_sugar = models.BooleanField(default=False, help_text="Содержит добавленный сахар (MG-501).")
    oil_tsp = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Расход масла в чайных ложках (MG-501).",
    )
    serving_size_label = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text='Подпись размера порции, напр. "1 тарелка / 200 г" (MG-501).',
    )

    # ── RB001_V_schema: новые поля чистой базы рецептов ──────────────────────
    dish_type = models.CharField(
        max_length=16,
        choices=DishType.choices,
        null=True,
        blank=True,
        help_text="Тип блюда (первое/второе/десерт...). RB-001.",
    )

    class PlateComponent(models.TextChoices):  # MG_STRAT_PLATE
        PROTEIN = "protein", "Plate: protein"
        CARB = "carb", "Plate: carb (side)"
        VEG = "veg", "Plate: veg/fiber"

    plate_component = models.CharField(  # MG_STRAT_PLATE
        max_length=8,
        choices=PlateComponent.choices,
        null=True,
        blank=True,
        help_text="Plate component for strategy=3 (manual tagging).",
    )

    portion_g = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Вес одной порции, г. RB-001.",
    )
    kcal_per_100g = models.DecimalField(
        max_digits=7,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Калорийность на 100 г готового блюда. RB-001.",
    )
    proteins_per_100g = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Белки на 100 г. RB-001.",
    )
    fats_per_100g = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Жиры на 100 г. RB-001.",
    )
    carbs_per_100g = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Углеводы на 100 г. RB-001.",
    )
    sugars_per_100g = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Сахара на 100 г. RB-001.",
    )
    cook_time_min = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Время приготовления, мин (число). RB-001.",
    )
    is_vegan = models.BooleanField(default=False, help_text="Веганское. RB-001.")
    is_vegetarian = models.BooleanField(default=False, help_text="Вегетарианское. RB-001.")
    is_gluten_free = models.BooleanField(default=False, help_text="Без глютена. RB-001.")
    is_lactose_free = models.BooleanField(default=False, help_text="Без лактозы. RB-001.")
    allergens = models.JSONField(default=list, blank=True, help_text="Список аллергенов. RB-001.")
    source = models.CharField(
        max_length=8,
        choices=Source.choices,
        default=Source.OWN,
        help_text="Источник рецепта. RB-001.",
    )

    class Meta:
        db_table = "recipes"
        indexes = [
            models.Index(fields=["legacy_id"]),
            models.Index(fields=["country"]),
            models.Index(fields=["author_id"]),
            models.Index(fields=["is_custom"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["food_group"]),
            models.Index(fields=["protein_type"]),
            models.Index(fields=["grain_type"]),
            models.Index(fields=["is_fatty_fish"]),
            models.Index(fields=["is_red_meat"]),
            models.Index(fields=["cooking_method"]),
            models.Index(fields=["has_added_sugar"]),
            GinIndex(fields=["suitable_for"], name="recipe_suitable_for_gin"),
            models.Index(fields=["dish_type"]),  # RB001_V_schema
            models.Index(fields=["source"]),
            models.Index(fields=["is_vegan"]),
            models.Index(fields=["is_vegetarian"]),
            models.Index(fields=["is_gluten_free"]),
            models.Index(fields=["is_lactose_free"]),
        ]

    def __str__(self):
        return self.title

    # MG_ALLERGEN14: держим allergens в синхроне с ингредиентами/названием.
    # Пересчитываем только при полном сохранении (без update_fields), чтобы не
    # мешать частичным .save(update_fields=[...]) и точечным .update() из команд.
    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is None:
            try:
                from apps.common.allergens import classify_recipe

                self.allergens = classify_recipe(self)
            except Exception:
                pass
        super().save(*args, **kwargs)


class RecipeAuthor(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонён"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="author_profile")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    motivation_text = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    recipes_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "recipe_authors"
        indexes = [models.Index(fields=["user_id"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Author({self.user}, {self.status})"


class DeletedRecipe(models.Model):
    """Рецепты, удалённые администратором. Используются для аудита и восстановления."""

    original_id = models.IntegerField(db_index=True)
    title = models.CharField(max_length=512)
    data = models.JSONField()
    deleted_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "deleted_recipes"
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"Deleted({self.original_id}, {self.title[:40]})"


class RecipeFavorite(models.Model):
    """Любимое/нелюбимое (per-user). is_favorite=True — любимое, False — нелюбимое."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipe_favorites")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="favorites")
    is_favorite = models.BooleanField(default=True, help_text="True=любимое, False=нелюбимое")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recipe_favorites"
        unique_together = [("user", "recipe")]
        indexes = [
            models.Index(fields=["user", "is_favorite"]),
            models.Index(fields=["recipe"]),
        ]

    def __str__(self):
        tag = "fav" if self.is_favorite else "dis"
        return f"{tag}({self.user_id}→{self.recipe_id})"


class ArchivedRecipe(models.Model):  # RB001_V_schema
    """Старая база рецептов (RB-001). Полная копия для аудита/восстановления."""

    original_id = models.IntegerField(db_index=True)
    title = models.CharField(max_length=512)
    data = models.JSONField(help_text="Полный снимок полей рецепта на момент архивации.")
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "archived_recipes"
        ordering = ["-archived_at"]
        indexes = [models.Index(fields=["original_id"])]

    def __str__(self):
        return f"Archived({self.original_id}, {self.title[:40]})"


# MG_RA002_cuisine_admin
class Cuisine(models.Model):
    """Editable list of country/cuisine names used in Recipe.country."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        db_table = "recipe_cuisines"
        ordering = ["sort_order", "name"]
        verbose_name = "Кухня / страна"
        verbose_name_plural = "Кухни / страны"

    def __str__(self):
        return self.name


# MG_IMPORT_TOOL_V1_session_model
class RecipeImportSession(models.Model):
    """Временная сессия импорта рецептов через Django Admin."""

    class Status(models.TextChoices):
        PENDING = "pending", "Загружен"
        PREVIEW = "preview", "Превью готово"
        DONE = "done", "Импортировано"
        ERROR = "error", "Ошибка"

    uploaded_file = models.FileField(upload_to="recipe_imports/", verbose_name="Файл xlsx")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Статус")
    preview_data = models.JSONField(default=list, blank=True, verbose_name="Данные превью")
    parse_errors = models.JSONField(default=list, blank=True, verbose_name="Ошибки парсинга")
    warnings = models.JSONField(default=list, blank=True, verbose_name="Предупреждения")
    recipes_count = models.PositiveIntegerField(default=0, verbose_name="Рецептов к импорту")
    imported_count = models.PositiveIntegerField(default=0, verbose_name="Импортировано")
    created_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Загрузил",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        db_table = "recipe_import_sessions"
        verbose_name = "Сессия импорта рецептов"
        verbose_name_plural = "Импорт рецептов (сессии)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"ImportSession #{self.pk} [{self.status}] {self.created_at:%Y-%m-%d %H:%M}"


# ── MG_RECIPELINK: recipe <-> rubricator product link ───────────────────────
class RecipeProduct(models.Model):
    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.CASCADE, related_name="product_links")
    product = models.ForeignKey(
        "fridge.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipe_links",
    )
    category_fk = models.ForeignKey(
        "fridge.ProductCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipe_links",
        db_column="category_id",
    )
    name_raw = models.CharField(max_length=255)
    name_canonical = models.CharField(max_length=255, blank=True)
    category_slug = models.CharField(max_length=64, blank=True)
    quantity = models.CharField(max_length=64, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    grams = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recipe_products"
        indexes = [
            models.Index(fields=["recipe"], name="recipe_prod_recipe_idx"),
            models.Index(fields=["product"], name="recipe_prod_product_idx"),
            models.Index(fields=["category_slug"], name="recipe_prod_catslug_idx"),
        ]

    def __str__(self):
        return "%s -> %s" % (self.name_raw, self.product_id)
