"""
MG-301: исключения генератора меню.

EmptyRolePoolError — поднимается, если для требуемой роли нет ни одного
подходящего рецепта (после применения hard-фильтров аллергий/нелюбимого).

Сообщение составляется на русском, понятным для не-технического пользователя
языком — оно проксируется в API ответ 400.
"""
# MG_301_V_exceptions
from __future__ import annotations
from typing import Optional


# человекочитаемые названия ролей
ROLE_LABELS_RU = {
    "protein":   "белковый компонент (мясо, рыба, бобы, яйца, творог)",
    "grain":     "зерновой/крахмалистый компонент (крупа, гарнир, хлеб)",
    "vegetable": "овощной компонент",
    "fruit":     "фруктовый компонент",
    "dairy":     "молочный компонент",
    "oil":       "масло/жир",
    "other":     "компонент",
}

MEAL_LABELS_RU = {
    "breakfast": "завтрака",
    "lunch":     "обеда",
    "dinner":    "ужина",
    "snack1":    "первого перекуса",
    "snack2":    "второго перекуса",
    "snack":     "перекуса",
}


class MenuGeneratorError(Exception):
    """Базовое исключение генератора меню."""

    code: str = "menu_generator_error"

    def to_response(self) -> dict:
        return {"error": self.code, "message": str(self)}


class EmptyRolePoolError(MenuGeneratorError):
    """
    Не нашлось рецептов нужной роли (food_group) для приёма пищи —
    после применения hard-фильтров (аллергии, нелюбимые продукты).
    """

    code = "empty_role_pool"

    def __init__(
        self,
        role: str,
        meal_slot: str,
        day_offset: int,
        member_name: Optional[str] = None,
        reason_hint: str = "",
    ):
        self.role = role
        self.meal_slot = meal_slot
        self.day_offset = day_offset
        self.member_name = member_name or ""
        self.reason_hint = reason_hint

        role_lbl = ROLE_LABELS_RU.get(role, role)
        meal_lbl = MEAL_LABELS_RU.get(meal_slot, meal_slot)
        day_n = day_offset + 1
        who = f" для {self.member_name}" if self.member_name else ""

        msg = (
            f"Не удалось подобрать {role_lbl}{who} "
            f"для {meal_lbl} (день {day_n}). "
        )
        if reason_hint:
            msg += f"{reason_hint} "
        msg += (
            "Возможные причины: слишком строгие фильтры (страна, время "
            "приготовления), список аллергий или нелюбимых продуктов "
            "исключил все подходящие рецепты, либо в базе пока мало "
            "рецептов этой группы. Попробуйте ослабить фильтры или "
            "уменьшить список исключений."
        )
        super().__init__(msg)

    def to_response(self) -> dict:
        return {
            "error": self.code,
            "message": str(self),
            "details": {
                "role": self.role,
                "meal_slot": self.meal_slot,
                "day_offset": self.day_offset,
                "member_name": self.member_name,
            },
        }
