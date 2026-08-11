"""MG_SPECACCESS: журнал действий специалиста в данных клиента.

Специалист меняет чужие данные. Без записи «кто и что» правка со стороны клиента
выглядит так, будто меню изменилось само — и разобраться потом нельзя ни ему, ни
поддержке. Пишем только изменения: чтение писать бессмысленно, журнал утонет в
просмотрах.

Запись журнала никогда не должна ронять само действие: если что-то пошло не так,
логируем ошибку и продолжаем.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_action(assignment, section: str, action: str, *, summary: str = "", member=None, object_id=None):
    """Записать действие специалиста. Возвращает запись журнала или None."""
    if assignment is None:
        return None
    from .models import SpecialistActionLog

    try:
        return SpecialistActionLog.objects.create(
            specialist=assignment.specialist,
            family=assignment.family,
            member=member,
            section=section,
            action=action,
            summary=summary[:500],
            object_id=object_id,
        )
    except Exception as exc:  # журнал не повод отменять сделанное
        logger.error("specialist action log failed: %s", exc)
        return None
