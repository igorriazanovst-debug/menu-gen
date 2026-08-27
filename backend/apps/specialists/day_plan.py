"""MG_COOK: наряд повара на день.

У тренера и нутрициолога петля информационная: посмотрел, оценил, назначил.
У повара — операционная: что готовить, на сколько человек, что для этого есть.
Поэтому здесь не аналитика, а наряд: блюда дня, порции, чего не хватает и что
пора использовать, пока не испортилось.

Всё берётся из существующих таблиц: `Menu`/`MenuItem` знают день и участника,
`RecipeProduct` — из чего блюдо, `FridgeItem` — что уже лежит.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

# Что считать «скоро испортится».
EXPIRING_DAYS = 3


def _menu_for_date(family, day):
    """Активное меню, покрывающее дату. Позже начатое — важнее."""
    from apps.menu.models import Menu

    return (
        Menu.objects.filter(family=family, start_date__lte=day, end_date__gte=day)
        .exclude(status=Menu.Status.ARCHIVED)
        .order_by("-start_date", "-id")
        .first()
    )


def _dish_key(item):
    """Одно блюдо приёма. В семейном меню блюдо продублировано под каждого
    участника — для повара это одно блюдо на N порций, а не N блюд."""
    return (item.meal_slot or item.meal_type, item.recipe_id, item.product_id, item.grams)


def day_plan(family, day=None) -> dict:
    """Наряд на день: приёмы, блюда с порциями, нехватка, скоропортящееся."""
    from apps.fridge.models import FridgeItem
    from apps.menu.models import MenuItem

    day = day or timezone.localdate()
    menu = _menu_for_date(family, day)
    if menu is None:
        return {
            "date": str(day),
            "menu_id": None,
            "meals": [],
            "missing": [],
            "expiring": _expiring(family, day),
        }

    offset = (day - menu.start_date).days
    items = (
        MenuItem.objects.filter(menu=menu, day_offset=offset)
        .select_related("recipe", "product", "member__user")
        .order_by("meal_slot", "id")
    )

    dishes: dict = {}
    for it in items:
        key = _dish_key(it)
        row = dishes.setdefault(
            key,
            {
                "slot": it.meal_slot or it.meal_type,
                "meal_type": it.meal_type,
                "title": (it.recipe.title if it.recipe_id else getattr(it.product, "name", "")) or "Без названия",
                "recipe_id": it.recipe_id,
                "product_id": it.product_id,
                "grams": it.grams,
                "servings": 0,
                "eaters": [],
            },
        )
        row["servings"] += 1
        name = getattr(getattr(it.member, "user", None), "name", None)
        if name and name not in row["eaters"]:
            row["eaters"].append(name)

    # Меню на всю семью (без разбивки по участникам) — порция одна, едоков
    # столько, сколько человек в семье. Иначе повар прочтёт «1 порция» на пятерых.
    from apps.family.models import FamilyMember

    family_size = FamilyMember.objects.filter(family=family).count()
    for row in dishes.values():
        if not row["eaters"]:
            row["servings"] = family_size or row["servings"]

    meals: dict = {}
    for row in dishes.values():
        meals.setdefault(row["slot"], []).append(row)

    stock = {
        (fi.product_id or fi.name.strip().lower()) for fi in FridgeItem.objects.filter(family=family, is_deleted=False)
    }
    missing = _missing_products(dishes.values(), stock)

    return {
        "date": str(day),
        "menu_id": menu.id,
        "meals": [{"slot": slot, "dishes": rows} for slot, rows in sorted(meals.items())],
        "missing": missing,
        "expiring": _expiring(family, day),
    }


def _missing_products(dishes, stock) -> list[dict]:
    """Продукты блюд дня, которых нет в холодильнике.

    Сверяем по связям рецепт→продукт: они уже посчитаны для списка покупок.
    Ингредиенты без связи в расчёт не идут — угадывать по строке значит
    показывать повару выдуманную нехватку.
    """
    from apps.recipes.models import RecipeProduct

    recipe_ids = [d["recipe_id"] for d in dishes if d["recipe_id"]]
    if not recipe_ids:
        return []

    seen = {}
    for link in (
        RecipeProduct.objects.filter(recipe_id__in=recipe_ids).select_related("product", "recipe").order_by("name_raw")
    ):
        key = link.product_id or (link.name_canonical or link.name_raw).strip().lower()
        if not key or key in stock or key in seen:
            continue
        seen[key] = {
            "name": (link.product.name if link.product_id else link.name_raw),
            "product_id": link.product_id,
            "for_dish": link.recipe.title,
        }
    return list(seen.values())


def _expiring(family, day) -> list[dict]:
    """Что испортится в ближайшие дни — это готовят в первую очередь."""
    from apps.fridge.models import FridgeItem

    cutoff = day + timedelta(days=EXPIRING_DAYS)
    rows = FridgeItem.objects.filter(
        family=family, is_deleted=False, expiry_date__isnull=False, expiry_date__lte=cutoff
    ).order_by("expiry_date")
    return [
        {
            "name": fi.name,
            "expiry_date": str(fi.expiry_date),
            "days_left": (fi.expiry_date - day).days,
            "quantity": str(fi.quantity or ""),
            "unit": fi.unit or "",
        }
        for fi in rows
    ]
