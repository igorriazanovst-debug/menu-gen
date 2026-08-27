# MG_RA002_cuisine_admin
from django.contrib import admin

from apps.common.search import AdminSearchMixin  # MG_YOSEARCH/MG_MORPHSEARCH

from .forms import RecipeAdminForm, RecipeChangelistForm
from .models import Cuisine, Recipe, RecipeAuthor, RecipeFavorite, RecipeImage

# Human help texts (meaning in DB + allowed values), translatable.
# MG_ADMINRU: подписи и пояснения — по-русски и прямо в коде.
#
# Раньше они лежали по-английски и переводились через .po. Каталог отставал
# (пятнадцать строк так и остались без перевода), а язык админки вдобавок
# зависел от Accept-Language браузера — при английском в браузере
# редактор рецептов открывался по-английски целиком.
#
# Тексты пишем сразу по-русски: продукт русскоязычный, а длинные пояснения с
# примерами через .po не живут — они устаревают первыми.
#
# Каждое пояснение отвечает на два вопроса: что сюда писать (с примером) и на
# что это влияет в приложении. Поле, про которое нельзя ответить на второй
# вопрос, скорее всего не нужно заполнять.
HELP = {
    "title": (
        "Название блюда так, как его увидит человек. "
        "Например: «Гречка с грибами» или «Сырники из творога 5%». "
        "Не пишите сюда вес и время — для них есть отдельные поля."
    ),
    "legacy_id": "Идентификатор из источника, откуда рецепт импортирован. Заполняется сам, менять нельзя.",
    "cook_time": (
        "Время готовки словами, как в источнике: «около 30 минут», «1 час 20 мин». "
        "Показывается в карточке. Для расчётов используется соседнее числовое поле."
    ),
    "cook_time_min": (
        "Время готовки в минутах, одним числом: 30. "
        "По нему работает фильтр «быстрые рецепты», поэтому заполняйте его, даже если время указано словами."
    ),
    "servings": "На сколько порций рассчитан рецепт по источнику. Например: 4.",
    "servings_normalized": (
        "Сколько порций считать генератору меню, если в источнике указано странно "
        "(«2–3 порции» или пусто). Оставьте пустым, если поле «Порций» заполнено числом."
    ),
    "portion_g": (
        "Вес одной порции в граммах: 250. "
        "Ключевое поле: по нему пересчитывается КБЖУ порции и собирается меню под коридор калорий. "
        "Без него рецепт не попадёт в стратегию «Тарелка»."
    ),
    "ingredients": (
        "Состав блюда. В каждой строке: название, количество, единица и вес в граммах. "
        "Например: «Гречка» · 1 · стакан · 200. "
        "Название выбирайте из подсказок — так ингредиент свяжется с продуктом из каталога, "
        "и рецепт будет попадать в подбор «что приготовить из холодильника». "
        "Своё название тоже можно вписать, если продукта в каталоге нет. "
        "Граммы обязательны: именно из них считается КБЖУ."
    ),
    "steps": (
        "Шаги приготовления, по одному действию в строке. "
        "Например: «Промыть гречку», «Залить водой 1:2», «Варить 15 минут под крышкой». "
        "Нумерация проставляется сама — не пишите «1.», «2.» вручную."
    ),
    "nutrition": ("Служебный объект с КБЖУ на 100 г. Заполняется автоматически из полей ниже — вручную не трогайте."),
    "categories": (
        "Свободные метки для поиска и подборок. Значения те же, что у типов блюда: "
        "soup, main, salad, side, dessert, drink, bakery, sauce, snack, breakfast_dish. "
        "Например, для окрошки — soup."
    ),
    "allergens": (
        "Аллергены в составе. Отмечайте по факту, а не «на всякий случай»: "
        "по этим отметкам блюдо исключается из меню тех, кто указал аллергию. "
        "Например, у сырников — milk (молоко) и eggs (яйца)."
    ),
    "suitable_for": (
        "В какие приёмы пищи блюдо уместно: завтрак, обед, ужин, перекус. "
        "Генератор ставит блюдо только в отмеченные слоты. "
        "Например, сырники — завтрак и перекус, но не ужин."
    ),
    "dish_type": (
        "Тип блюда: первое, основное, салат, гарнир, десерт, напиток, выпечка, соус, перекус, завтрак. "
        "Определяет, в какую роль в меню блюдо встанет. Одно значение."
    ),
    "plate_component": (
        "Роль в «Тарелке»: белок, гарнир или овощи. "
        "Заполняйте у простых моно-блюд (отварной рис — гарнир, куриная грудка — белок). "
        "У составных блюд оставьте пустым."
    ),
    "food_group": (
        "Основная группа продуктов: крупы, белок, овощи, фрукты, молочное, масло, прочее. "
        "По ней балансируется недельное меню, чтобы не выходило семь круп подряд."
    ),
    "protein_type": (
        "Происхождение белка: животный, растительный, смешанный. " "Нужно для вегетарианских и постных меню."
    ),
    "grain_type": "Тип крупы: цельная или очищенная. Например, бурый рис — цельная, белый — очищенная.",
    "cooking_method": (
        "Способ приготовления: варка, запекание, жарка, гриль, сырое, тушение, на пару. "
        "Используется, чтобы в одном дне не оказалось три жареных блюда подряд."
    ),
    "source": (
        "Откуда взялся рецепт: own — наш собственный, import — из внешней базы, "
        "user — добавил пользователь, parsed — распарсен с сайта. "
        "На видимость не влияет, нужен для разбора качества базы."
    ),
    "country": "Кухня или страна: «Русская», «Итальянская». Показывается в карточке и работает как фильтр.",
    "oil_tsp": (
        "Сколько чайных ложек масла уходит на блюдо: 2. "
        "Учитывается в подсчёте жиров — на глаз масло почти всегда недооценивают."
    ),
    "serving_size_label": (
        "Как назвать порцию человеческим языком: «1 тарелка (250 г)», «2 сырника». "
        "Показывается рядом с КБЖУ, чтобы цифры были понятны без весов."
    ),
    "has_added_sugar": "Есть ли добавленный сахар (не считая сахара самих фруктов и молока).",
    "is_fatty_fish": "Жирная рыба: лосось, скумбрия, сельдь. Нужно для рекомендаций по омега-3.",
    "is_red_meat": "Красное мясо: говядина, свинина, баранина. Ограничивается в части диет.",
    "is_vegan": "Без продуктов животного происхождения вообще, включая мёд и молоко.",
    "is_vegetarian": "Без мяса и рыбы, но молоко и яйца допустимы.",
    "is_gluten_free": "Без глютена: без пшеницы, ржи, ячменя и обычного овса.",
    "is_lactose_free": "Без лактозы. Твёрдые выдержанные сыры обычно можно, молоко и творог — нет.",
    "is_custom": "Рецепт добавил пользователь, а не редакция. В общую базу такие не попадают.",
    "is_published": (
        "Показывать людям. Снимите галочку, пока рецепт не дописан: "
        "неопубликованный рецепт не появится ни в поиске, ни в генераторе меню."
    ),
    "image_url": "Обложка блюда. Загрузите файл кнопкой ниже или вставьте ссылку. Первый кадр в карточке.",
    "video_url": "Ссылка на видео с приготовлением. Необязательно.",
    "source_url": "Адрес страницы-источника, если рецепт откуда-то взят. Нужен, чтобы можно было свериться.",
    "kcal": "Калорийность одной порции. Считается из значений на 100 г и веса порции — вручную не нужно.",
    "proteins": "Белки в одной порции, г. Считается автоматически.",
    "fats": "Жиры в одной порции, г. Считается автоматически.",
    "carbs": "Углеводы в одной порции, г. Считается автоматически.",
    "kcal_per_100g": (
        "Калорийность 100 г готового блюда. "
        "Это основа всех расчётов: из неё и веса порции получается КБЖУ порции. "
        "Берите с этикетки или из справочника, а не «на глаз»."
    ),
    "proteins_per_100g": "Белки на 100 г готового блюда.",
    "fats_per_100g": "Жиры на 100 г готового блюда.",
    "carbs_per_100g": "Углеводы на 100 г готового блюда.",
    "sugars_per_100g": "Сахара на 100 г — часть углеводов, не добавляются к ним сверху.",
}

LABELS = {
    "title": "Название",
    "legacy_id": "Идентификатор источника",
    "cook_time": "Время готовки (словами)",
    "cook_time_min": "Время готовки, мин",
    "servings": "Порций",
    "servings_normalized": "Порций (для расчёта)",
    "portion_g": "Вес порции, г",
    "ingredients": "Состав",
    "steps": "Приготовление",
    "nutrition": "КБЖУ (служебное)",
    "categories": "Метки",
    "allergens": "Аллергены",
    "suitable_for": "Для приёмов пищи",
    "dish_type": "Тип блюда",
    "plate_component": "Роль в «Тарелке»",
    "food_group": "Группа продуктов",
    "protein_type": "Тип белка",
    "grain_type": "Тип крупы",
    "cooking_method": "Способ приготовления",
    "source": "Происхождение",
    "country": "Кухня / страна",
    "oil_tsp": "Масло, ч. л.",
    "serving_size_label": "Порция словами",
    "has_added_sugar": "Добавленный сахар",
    "is_fatty_fish": "Жирная рыба",
    "is_red_meat": "Красное мясо",
    "is_vegan": "Веганское",
    "is_vegetarian": "Вегетарианское",
    "is_gluten_free": "Без глютена",
    "is_lactose_free": "Без лактозы",
    "is_custom": "Пользовательский",
    "is_published": "Опубликован",
    "image_url": "Обложка",
    "video_url": "Видео",
    "source_url": "Ссылка на источник",
    "kcal": "Калории / порция",
    "proteins": "Белки / порция",
    "fats": "Жиры / порция",
    "carbs": "Углеводы / порция",
    "kcal_per_100g": "Калории / 100 г",
    "proteins_per_100g": "Белки / 100 г",
    "fats_per_100g": "Жиры / 100 г",
    "carbs_per_100g": "Углеводы / 100 г",
    "sugars_per_100g": "Сахара / 100 г",
}


@admin.register(Cuisine)
class CuisineAdmin(AdminSearchMixin, admin.ModelAdmin):
    list_display = ("id", "name", "sort_order", "is_active")
    list_editable = ("name", "sort_order", "is_active")
    search_fields = ("name",)
    ordering = ("sort_order", "name")


class RecipeImageInline(admin.TabularInline):
    """MG_GALLERY: дополнительные фото блюда прямо в карточке рецепта.

    Обложка (Recipe.image_url) остаётся отдельным полем и идёт первым слайдом —
    сюда добавляются только остальные ракурсы.
    """

    model = RecipeImage
    extra = 1
    fields = ("preview", "image", "caption", "sort_order")
    readonly_fields = ("preview",)
    verbose_name = "Фото"
    verbose_name_plural = "Фотогалерея (кроме обложки)"

    @admin.display(description="Превью")
    def preview(self, obj):
        from django.utils.html import format_html

        if not obj or not obj.pk or not obj.image:
            return "—"
        return format_html('<img src="{}" style="height:60px;border-radius:6px" />', obj.image.url)


@admin.register(Recipe)
class RecipeAdmin(AdminSearchMixin, admin.ModelAdmin):
    form = RecipeAdminForm
    inlines = (RecipeImageInline,)  # MG_GALLERY

    # MG_ADMINUPLOAD: загрузка файла — своей админской ручкой, а не публичным API.
    #
    # Кнопка «Загрузить файл» ходила в /api/v1/recipes/upload-media/, а тот
    # авторизует по JWT: браузер в админке шлёт только сессионную куку, и на проде
    # запрос приходил анонимным — «Upload failed: Error: 401». Здесь же
    # авторизация ровно та, которой открыта сама страница админки: сессия и
    # проверка на staff, встроенная в admin_view.
    def get_urls(self):
        from django.urls import path as _p

        return [
            _p(
                "upload-media/",
                self.admin_site.admin_view(self.upload_media_view),
                name="recipes_recipe_upload_media",
            ),
            # MG_INGPICK: подсказки по каталогу для поля ингредиента.
            _p(
                "ingredient-search/",
                self.admin_site.admin_view(self.ingredient_search_view),
                name="recipes_recipe_ingredient_search",
            ),
        ] + super().get_urls()

    # MG_INGPICK: поиск продукта для строки состава.
    #
    # Название ингредиента набиралось руками, и одно и то же писали по-разному
    # («лук репчатый», «репчатый лук», «лук»). Связь рецепта с продуктом
    # каталога строится по названию, поэтому каждый новый вариант написания —
    # это рецепт, который не найдётся в подборе «из холодильника».
    #
    # Отдаём только каталог: справочники штрих-кодов (retail, off_bulk) и
    # догадки ИИ — это 32 тысячи конкретных упаковок, и в подсказках к составу
    # они бы утопили один «Лук репчатый» полусотней банок.
    def ingredient_search_view(self, request):
        from django.http import JsonResponse

        from apps.common.search import search_q
        from apps.fridge.models import Product
        from apps.fridge.visibility import catalog_q

        q = (request.GET.get("q") or "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        rows = (
            Product.objects.filter(catalog_q())
            .filter(search_q(Product, ["name"], q))
            .order_by("name")
            .values("name", "default_unit")[:20]
        )
        return JsonResponse({"results": [{"name": r["name"], "unit": r["default_unit"] or ""} for r in rows]})

    # MG_LINKASYNC: связи с продуктами строит ИИ — это десятки секунд, и раньше
    # сохранение рецепта ждало их прямо в запросе (регулярный 504 от nginx).
    # Теперь пересборка уходит в очередь, и об этом надо сказать: иначе
    # непонятно, почему состав изменился, а связи ещё старые.
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change or "ingredients" in getattr(form, "changed_data", ()):
            from django.contrib import messages

            self.message_user(
                request,
                "Состав изменён — связи с продуктами пересобираются в фоне. "
                "Через минуту обновите страницу, чтобы увидеть результат.",
                messages.INFO,
            )

    def upload_media_view(self, request):
        from django.http import JsonResponse

        from .media_upload import save_media

        if request.method != "POST":
            return JsonResponse({"detail": "Только POST."}, status=405)

        path, error = save_media(request.FILES.get("file"), request.POST.get("media_type", "image"))
        if error:
            return JsonResponse({"detail": error}, status=400)
        return JsonResponse({"url": request.build_absolute_uri(path)})

    list_display = (
        "id",
        "title",
        "dish_type",
        "country",
        "source",
        "is_custom",
        "is_published",
        "author",
        "created_at",
    )
    list_editable = ("title", "dish_type", "country", "source")

    # MG_RA002b_country_select_list
    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault("form", RecipeChangelistForm)
        return super().get_changelist_form(request, **kwargs)

    list_filter = (
        "dish_type",
        "source",
        "food_group",
        "is_custom",
        "is_published",
        "is_vegan",
        "is_vegetarian",
        "country",
    )
    search_fields = ("title", "legacy_id")
    autocomplete_fields = ("author",)
    readonly_fields = ("legacy_id", "created_at", "updated_at")
    actions = ["publish", "unpublish"]
    save_on_top = True

    fieldsets = (
        (
            "Основное",
            {
                "description": (
                    "Что человек увидит в карточке блюда. Пока не стоит галочка «Опубликован», "
                    "рецепт не виден никому, кроме редакции."
                ),
                "fields": (
                    "title",
                    "country",
                    "source",
                    "is_custom",
                    "is_published",
                    "author",
                    "image_url",
                    "video_url",
                    "source_url",
                ),
            },
        ),
        (
            "Состав и приготовление",
            {
                "description": (
                    "Состав — основа всего: из граммов считается КБЖУ, а по названиям "
                    "рецепт связывается с продуктами каталога и попадает в подбор "
                    "«что приготовить из холодильника». Выбирайте названия из подсказок."
                ),
                "fields": ("ingredients", "steps"),
            },
        ),
        (
            "Классификация — как блюдо попадёт в меню",
            {
                "description": (
                    "Эти поля решают, в какой день и в какой приём пищи генератор поставит блюдо "
                    "и с чем его сочетает. Заполнять по факту: неверная классификация портит меню "
                    "заметнее, чем незаполненная."
                ),
                "fields": (
                    "dish_type",
                    "plate_component",
                    "categories",
                    "suitable_for",
                    "food_group",
                    "protein_type",
                    "grain_type",
                    "cooking_method",
                ),
            },
        ),
        (
            "Ограничения и аллергены",
            {
                "description": (
                    "По этим отметкам блюдо ИСКЛЮЧАЕТСЯ из меню людей с аллергией или диетой. "
                    "Ошибка здесь — не косметическая: лишняя галочка прячет блюдо, "
                    "недостающая отправляет аллергену то, что ему нельзя."
                ),
                "fields": (
                    "is_vegan",
                    "is_vegetarian",
                    "is_gluten_free",
                    "is_lactose_free",
                    "is_fatty_fish",
                    "is_red_meat",
                    "has_added_sugar",
                    "allergens",
                ),
            },
        ),
        (
            "Порция и время",
            {
                "description": (
                    "«Вес порции» — обязательное поле: без него КБЖУ порции не посчитать "
                    "и блюдо не попадёт в подбор под коридор калорий."
                ),
                "fields": (
                    "servings",
                    "servings_normalized",
                    "portion_g",
                    "serving_size_label",
                    "cook_time",
                    "cook_time_min",
                    "oil_tsp",
                ),
            },
        ),
        (
            "КБЖУ",
            {
                # MG_KBJU_ADMIN: объект `nutrition` больше не редактируется вручную —
                # система собирает его из полей на 100 г при сохранении.
                "fields": (
                    "kcal",
                    "proteins",
                    "fats",
                    "carbs",
                    "kcal_per_100g",
                    "proteins_per_100g",
                    "fats_per_100g",
                    "carbs_per_100g",
                    "sugars_per_100g",
                ),
                "description": (
                    "Заполняйте значения НА 100 Г — верхние поля «на порцию» система посчитает сама "
                    "из веса порции. Служебный объект nutrition тоже собирается автоматически."
                ),
            },
        ),
        (
            "Служебное",
            {
                "description": "Проставляется системой. Нужно, чтобы понять, откуда рецепт взялся и когда менялся.",
                "fields": ("legacy_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, field in form.base_fields.items():
            if name in LABELS:
                field.label = LABELS[name]
            if name in HELP:
                field.help_text = HELP[name]
        return form

    @admin.action(description="Опубликовать выбранные")
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Снять с публикации")
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "applied_at", "approved_at")
    list_filter = ("status",)
    autocomplete_fields = ("user",)
    actions = ["approve", "reject"]

    @admin.action(description="Одобрить заявки")
    def approve(self, request, queryset):
        from django.utils import timezone

        from apps.users.models import User

        now = timezone.now()
        for obj in queryset:
            obj.status = "approved"
            obj.approved_at = now
            obj.save(update_fields=["status", "approved_at"])
            User.objects.filter(id=obj.user_id).update(user_type="recipe_author")

    @admin.action(description="Отклонить заявки")
    def reject(self, request, queryset):
        queryset.update(status="rejected")


@admin.register(RecipeFavorite)
class RecipeFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "recipe", "is_favorite", "created_at")
    list_filter = ("is_favorite",)
    autocomplete_fields = ("user",)
    raw_id_fields = ("recipe",)
    search_fields = ("recipe__title", "user__email", "user__name")


# MG_IMPORT_TOOL_V1_admin
from django.urls import path as _url_path  # noqa: E402

from .admin_import_views import ImportPreviewView, ImportUploadView  # noqa: E402
from .models import RecipeImportSession  # noqa: E402


@admin.register(RecipeImportSession)
class RecipeImportSessionAdmin(admin.ModelAdmin):
    change_list_template = "admin/recipes/recipeimportsession_changelist.html"
    list_display = ("id", "status", "recipes_count", "imported_count", "created_by", "created_at")
    list_filter = ("status",)
    readonly_fields = (
        "status",
        "preview_data",
        "parse_errors",
        "warnings",
        "recipes_count",
        "imported_count",
        "created_by",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            _url_path(
                "upload/",
                self.admin_site.admin_view(ImportUploadView.as_view()),
                name="recipes_recipeimportsession_upload",
            ),
            _url_path(
                "<int:session_pk>/preview/",
                self.admin_site.admin_view(
                    lambda req, session_pk: ImportPreviewView.as_view()(req, session_pk=session_pk)
                ),
                name="recipes_recipeimportsession_preview",
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["upload_url"] = "upload/"
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and obj.status == RecipeImportSession.Status.PREVIEW:
            extra_context["preview_url"] = f"../{object_id}/preview/"
        return super().change_view(request, object_id, form_url, extra_context)
