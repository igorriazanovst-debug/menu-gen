"""MG_MENUAPPLY: выдать составленное меню клиенту.

Конструктор строит `ConstructedMenu` — гибкую структуру со свободными
названиями приёмов. Клиент такой структуры не знает: у него есть `Menu` с
приёмами `breakfast/lunch/dinner/snack`, и на нём держится всё остальное —
дневник с планом-фактом, список покупок, мобильное приложение.

Поэтому меню не показывается клиенту «как есть», а разворачивается в обычное
меню семьи. Иначе пришлось бы заводить второй тип меню на клиентской стороне и
переучивать под него дневник, покупки и приложение.

До этого выдать меню было нельзя вовсе: эндпоинты конструктора отдают только
`author=request.user`, то есть специалист составлял неделю в пустоту.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction

from .models import ConstructedMenu, Menu, MenuItem

# Название приёма в конструкторе — свободный текст. Сначала пытаемся понять его,
# и только если не вышло — расставляем по порядку.
_NAME_TO_SLOT = (
    ("завтрак", "breakfast", MenuItem.MealType.BREAKFAST),
    ("обед", "lunch", MenuItem.MealType.LUNCH),
    ("ужин", "dinner", MenuItem.MealType.DINNER),
    ("перекус", "snack", MenuItem.MealType.SNACK),
    ("полдник", "snack", MenuItem.MealType.SNACK),
    ("ланч", "snack", MenuItem.MealType.SNACK),
)

# Раскладка по порядку приёма в дне, когда по названию не понять.
_BY_ORDER = [
    ("breakfast", MenuItem.MealType.BREAKFAST),
    ("lunch", MenuItem.MealType.LUNCH),
    ("dinner", MenuItem.MealType.DINNER),
]


def _slot_by_name(name: str):
    low = (name or "").strip().lower()
    for needle, slot, meal_type in _NAME_TO_SLOT:
        if needle in low:
            return slot, meal_type
    return None


def resolve_slots(meals):
    """Приёмы одного дня → список (meal_slot, meal_type) в том же порядке.

    Перекусы нумеруются (`snack1`, `snack2`): мобильное приложение различает
    слоты по этим именам, и два одинаковых `snack` слиплись бы в один.
    """
    resolved = []
    unnamed_order = 0
    for meal in meals:
        by_name = _slot_by_name(getattr(meal, "name", ""))
        if by_name:
            resolved.append(list(by_name))
            continue
        if unnamed_order < len(_BY_ORDER):
            resolved.append(list(_BY_ORDER[unnamed_order]))
        else:
            resolved.append(["snack", MenuItem.MealType.SNACK])
        unnamed_order += 1

    snack_no = 0
    for pair in resolved:
        if pair[0] == "snack":
            snack_no += 1
            pair[0] = f"snack{snack_no}"
    return [tuple(p) for p in resolved]


def _meal_plan_type(days_meals) -> str:
    """«3» или «5» — по самому насыщенному дню.

    Мобильное приложение читает это из `filters_used`, чтобы решить, показывать
    ли строки перекусов. Без пометки оно угадывает по составу — и на меню без
    перекусов рисует пустые слоты.
    """
    biggest = max((len(m) for m in days_meals), default=0)
    return "5" if biggest > 3 else "3"


@transaction.atomic
def apply_to_family(constructed: ConstructedMenu, start_date, actor_user) -> Menu:
    """Развернуть составленное меню в меню семьи клиента. Возвращает Menu."""
    family = constructed.client_family
    if family is None:
        raise ValueError("Меню не привязано к клиенту.")

    meals = list(constructed.meals.prefetch_related("items").all())
    by_day: dict[int, list] = {}
    for meal in meals:
        by_day.setdefault(meal.day_index, []).append(meal)
    for day in by_day.values():
        day.sort(key=lambda m: (m.order, m.id))

    days = max(constructed.days, (max(by_day) + 1) if by_day else 1)

    menu = Menu.objects.create(
        family=family,
        creator_id=actor_user.id,
        period_days=days,
        start_date=start_date,
        end_date=start_date + timedelta(days=days - 1),
        status=Menu.Status.ACTIVE,
        modified_by=Menu.ModifiedBy.SPECIALIST,
        filters_used={
            "source": "constructor",
            "constructed_menu_id": constructed.id,
            "meal_plan_type": _meal_plan_type(list(by_day.values())),
        },
    )

    rows = []
    for day_index, day_meals in by_day.items():
        slots = resolve_slots(day_meals)
        for meal, (slot, meal_type) in zip(day_meals, slots):
            for item in meal.items.all():
                rows.append(
                    MenuItem(
                        menu=menu,
                        recipe=item.recipe,
                        product=item.product,
                        grams=item.grams,
                        # Меню выдаётся семье целиком: в конструкторе разбивки по
                        # участникам нет, и придумывать её здесь нельзя.
                        member=None,
                        meal_type=meal_type,
                        meal_slot=slot,
                        day_offset=day_index,
                        quantity=item.quantity,
                    )
                )
    MenuItem.objects.bulk_create(rows)

    constructed.status = ConstructedMenu.Status.PUBLISHED
    constructed.applied_menu = menu
    constructed.save(update_fields=["status", "applied_menu", "updated_at"])
    return menu
