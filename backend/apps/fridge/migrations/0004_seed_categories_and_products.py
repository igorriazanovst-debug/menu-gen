"""Seed ProductCategory + basic Product + remap legacy Product.category strings."""
from django.db import migrations


CATEGORIES = [
    ("dairy",      "Молочные продукты", "🥛", "#E3F2FD", 10),
    ("meat",       "Мясо и птица",      "🍖", "#FFCDD2", 20),
    ("fish",       "Рыба и морепродукты","🐟", "#B3E5FC", 30),
    ("vegetables", "Овощи",             "🥦", "#C8E6C9", 40),
    ("fruits",     "Фрукты и ягоды",    "🍎", "#FFE0B2", 50),
    ("grains",     "Крупы и макароны",  "🌾", "#FFF9C4", 60),
    ("bakery",     "Хлеб и выпечка",    "🥖", "#FFECB3", 70),
    ("eggs",       "Яйца",              "🥚", "#FFF8E1", 80),
    ("oils",       "Масла и соусы",     "🫒", "#F0F4C3", 90),
    ("drinks",     "Напитки",           "🥤", "#B2EBF2", 100),
    ("frozen",     "Заморозка",         "🧊", "#E1F5FE", 110),
    ("sweets",     "Сладости",          "🍫", "#F8BBD0", 120),
    ("condiments", "Специи и приправы", "🧂", "#D7CCC8", 130),
    ("other",      "Прочее",            "📦", "#ECEFF1", 999),
]

SEED_PRODUCTS = {
    "dairy": [
        ("Молоко", "л", 60),
        ("Кефир", "л", 40),
        ("Сметана", "г", 200),
        ("Творог", "г", 110),
        ("Сыр", "г", 350),
        ("Йогурт", "шт", 75),
        ("Сливочное масло", "г", 740),
    ],
    "meat": [
        ("Курица (филе)", "г", 110),
        ("Говядина", "г", 180),
        ("Свинина", "г", 240),
        ("Фарш", "г", 200),
        ("Колбаса", "г", 280),
    ],
    "fish": [
        ("Лосось", "г", 200),
        ("Треска", "г", 80),
        ("Тунец", "г", 130),
        ("Креветки", "г", 90),
    ],
    "vegetables": [
        ("Картофель", "г", 80),
        ("Морковь", "г", 35),
        ("Лук", "г", 40),
        ("Чеснок", "г", 145),
        ("Помидоры", "г", 20),
        ("Огурцы", "г", 15),
        ("Перец болгарский", "г", 25),
        ("Капуста", "г", 25),
        ("Кабачки", "г", 25),
    ],
    "fruits": [
        ("Яблоки", "г", 50),
        ("Бананы", "г", 90),
        ("Апельсины", "г", 45),
        ("Лимоны", "г", 30),
        ("Виноград", "г", 70),
    ],
    "grains": [
        ("Рис", "г", 340),
        ("Гречка", "г", 330),
        ("Овсянка", "г", 370),
        ("Макароны", "г", 350),
    ],
    "bakery": [
        ("Хлеб белый", "шт", 250),
        ("Хлеб чёрный", "шт", 200),
        ("Батон", "шт", 260),
    ],
    "eggs": [
        ("Яйца куриные", "шт", 70),
    ],
    "oils": [
        ("Подсолнечное масло", "л", 880),
        ("Оливковое масло", "л", 880),
        ("Майонез", "г", 620),
    ],
    "drinks": [
        ("Сок апельсиновый", "л", 45),
        ("Минеральная вода", "л", 0),
    ],
    "frozen": [
        ("Замороженные овощи", "г", 35),
        ("Пельмени", "г", 240),
    ],
    "sweets": [
        ("Шоколад", "г", 540),
        ("Печенье", "г", 430),
    ],
    "condiments": [
        ("Соль", "г", 0),
        ("Сахар", "г", 400),
        ("Перец чёрный", "г", 250),
    ],
    "other": [],
}

LEGACY_TOKEN_MAP = [
    ("молочн", "dairy"), ("dairy", "dairy"), ("milk", "dairy"), ("cheese", "dairy"),
    ("yogurt", "dairy"), ("творог", "dairy"), ("сыр", "dairy"), ("сметан", "dairy"),
    ("мясо", "meat"), ("meat", "meat"), ("chicken", "meat"), ("beef", "meat"),
    ("pork", "meat"), ("курица", "meat"), ("говядин", "meat"), ("свинин", "meat"),
    ("колбас", "meat"),
    ("fish", "fish"), ("seafood", "fish"), ("рыб", "fish"), ("креветк", "fish"),
    ("лосось", "fish"), ("тунец", "fish"),
    ("vegetabl", "vegetables"), ("овощ", "vegetables"), ("картофел", "vegetables"),
    ("морковь", "vegetables"), ("помидор", "vegetables"), ("огурц", "vegetables"),
    ("fruit", "fruits"), ("фрукт", "fruits"), ("яблок", "fruits"), ("банан", "fruits"),
    ("grain", "grains"), ("крупа", "grains"), ("крупы", "grains"),
    ("макарон", "grains"), ("pasta", "grains"), ("rice", "grains"),
    ("bread", "bakery"), ("bakery", "bakery"), ("хлеб", "bakery"), ("выпечк", "bakery"),
    ("egg", "eggs"), ("яйц", "eggs"),
    ("oil", "oils"), ("масл", "oils"), ("sauce", "oils"), ("соус", "oils"),
    ("condiment", "condiments"), ("spice", "condiments"), ("припра", "condiments"),
    ("соль", "condiments"), ("сахар", "condiments"),
    ("drink", "drinks"), ("beverag", "drinks"), ("juice", "drinks"),
    ("сок", "drinks"), ("вод", "drinks"), ("напит", "drinks"),
    ("frozen", "frozen"), ("заморо", "frozen"),
    ("sweet", "sweets"), ("candy", "sweets"), ("chocolate", "sweets"),
    ("шокола", "sweets"), ("конфет", "sweets"),
]


def map_legacy_to_slug(legacy: str) -> str:
    s = (legacy or "").strip().lower()
    if not s:
        return "other"
    for token, slug in LEGACY_TOKEN_MAP:
        if token in s:
            return slug
    return "other"


def seed(apps, schema_editor):
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    Product = apps.get_model("fridge", "Product")

    slug_to_cat = {}
    for slug, name_ru, icon, color, sort_order in CATEGORIES:
        cat, _ = ProductCategory.objects.update_or_create(
            slug=slug,
            defaults={
                "name_ru": name_ru,
                "icon": icon,
                "color": color,
                "sort_order": sort_order,
                "is_active": True,
            },
        )
        slug_to_cat[slug] = cat

    for slug, items in SEED_PRODUCTS.items():
        cat = slug_to_cat[slug]
        for name, unit, kcal in items:
            Product.objects.update_or_create(
                name=name,
                barcode=None,
                defaults={
                    "category": cat.name_ru,
                    "category_fk": cat,
                    "default_unit": unit,
                    "calories_per_100g": kcal,
                    "is_seed": True,
                },
            )

    for p in Product.objects.filter(category_fk__isnull=True):
        slug = map_legacy_to_slug(p.category)
        p.category_fk = slug_to_cat[slug]
        p.save(update_fields=["category_fk"])


def unseed(apps, schema_editor):
    ProductCategory = apps.get_model("fridge", "ProductCategory")
    Product = apps.get_model("fridge", "Product")
    Product.objects.filter(is_seed=True).delete()
    Product.objects.update(category_fk=None)
    ProductCategory.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("fridge", "0003_product_category_fk")]
    operations = [migrations.RunPython(seed, reverse_code=unseed)]
