"""MG_SPECACCESS: что специалист может делать с данными клиента.

Одно место, где записано правило доступа. До этого проверка была одна на всех:
«верифицированный специалист с активным назначением» — и дальше любой из них мог
всё. Тренеру открывался холодильник, повару — коридор калорий клиента.

Правило состоит из двух частей, и обе обязательны:

1. Назначение. Доступ живёт ровно столько, сколько живёт активное
   SpecialistAssignment между этим специалистом и семьёй. Завершили с любой
   стороны — доступа нет в ту же секунду.
2. Роль. В каком качестве специалиста позвали, то он и может (см. таблицу).

Роль берётся из назначения, а не из профиля специалиста: человек может быть
диетологом «вообще», но в конкретную семью его позвали поваром — и права у него
поварские. В старых назначениях поле пустое, тогда берём тип из профиля.

Таблица — не документация, а исполняемый код: интерфейс, права и тесты читают её,
а не повторяют своими словами.
"""

from __future__ import annotations

from django.db import models


class Section(models.TextChoices):
    """Разделы данных клиента."""

    PROFILE = "profile", "Профиль и коридор калорий"
    DIARY = "diary", "Дневник питания"
    MENU = "menu", "Меню"
    FRIDGE = "fridge", "Холодильник"
    SHOPPING = "shopping", "Списки покупок"


class Level(models.TextChoices):
    NONE = "none", "Нет доступа"
    READ = "read", "Чтение"
    WRITE = "write", "Правка"


# Тип специалиста → раздел → уровень. Разделы, которых нет в словаре роли,
# считаются закрытыми: забыть открыть безопаснее, чем забыть закрыть.
MATRIX: dict[str, dict[str, str]] = {
    "dietitian": {
        Section.PROFILE: Level.WRITE,
        Section.DIARY: Level.READ,
        Section.MENU: Level.WRITE,
        Section.FRIDGE: Level.READ,
    },
    "trainer": {
        Section.PROFILE: Level.WRITE,
        Section.DIARY: Level.READ,
        Section.MENU: Level.READ,
    },
    # Личный повар ведёт закупку и готовку, поэтому правит холодильник и списки
    # всей семьи. Профиль ему виден только для чтения (аллергии, нелюбимое),
    # дневник питания не нужен вовсе — это личное.
    "cook": {
        Section.PROFILE: Level.READ,
        Section.MENU: Level.WRITE,
        Section.FRIDGE: Level.WRITE,
        Section.SHOPPING: Level.WRITE,
    },
}

_ORDER = {Level.NONE: 0, Level.READ: 1, Level.WRITE: 2}


def level_for(specialist_type: str, section: str) -> str:
    """Уровень доступа роли к разделу."""
    return MATRIX.get(specialist_type or "", {}).get(section, Level.NONE)


def permissions_for(specialist_type: str) -> dict[str, str]:
    """Вся строка таблицы — для интерфейса: что показывать, а что прятать."""
    return {section.value: level_for(specialist_type, section) for section in Section}


def role_of(assignment) -> str:
    """Роль, в которой специалист работает с этой семьёй."""
    return getattr(assignment, "specialist_type", "") or getattr(assignment.specialist, "specialist_type", "")


def allows(assignment, section: str, *, write: bool = False) -> bool:
    """Разрешено ли действие в разделе по этому назначению."""
    if assignment is None:
        return False
    needed = Level.WRITE if write else Level.READ
    return _ORDER[level_for(role_of(assignment), section)] >= _ORDER[needed]


def active_assignment(specialist, family_id):
    """Активное назначение специалиста на семью. None — доступа нет.

    Единственный способ добраться до данных клиента: раньше эта проверка была
    выписана в каждой вьюхе кабинета отдельно, и забыть её было легко.
    """
    if specialist is None or family_id is None:
        return None
    from .models import SpecialistAssignment

    return (
        SpecialistAssignment.objects.filter(
            specialist=specialist,
            family_id=family_id,
            status=SpecialistAssignment.Status.ACTIVE,
        )
        .select_related("specialist")
        .first()
    )
