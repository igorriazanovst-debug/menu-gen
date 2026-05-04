"""
MG-205: единая точка записи правок целей КБЖУ.

record_target_change():
  1) пишет ProfileTargetAudit (история по полю)
  2) дублирует в общий AuditLog (entity_type='profile_target')

Используется из nutrition.fill_profile_targets и из serializers (PATCH).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

MG_205_V = 1


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def record_target_change(
    profile,
    field: str,
    new_value,
    source: str,
    by_user=None,
    old_value=None,
    reason: str = "",
) -> None:
    """Записать изменение цели КБЖУ в ProfileTargetAudit + AuditLog.

    Args:
        profile: instance Profile
        field: одно из 'calorie_target', 'protein_target_g',
               'fat_target_g', 'carb_target_g', 'fiber_target_g'
        new_value: новое значение (число / Decimal / None)
        source: 'auto' | 'user' | 'specialist'
        by_user: instance User или None (для 'auto' всегда None)
        old_value: предыдущее значение (для diff)
        reason: текстовый комментарий
    """
    # local imports — избегаем циклических зависимостей при загрузке Django
    from .models import ProfileTargetAudit

    nv = _to_decimal(new_value)
    ov = _to_decimal(old_value)

    pta = ProfileTargetAudit.objects.create(
        profile=profile,
        field=field,
        source=source,
        by_user=by_user,
        old_value=ov,
        new_value=nv,
        reason=reason or "",
    )

    # Дублируем в общий AuditLog (мягко: если приложение sync/AuditLog
    # недоступно — не падаем, чтобы не блокировать save())
    try:
        from apps.sync.models import AuditLog

        AuditLog.objects.create(
            user=by_user,
            action="profile_target.update",
            entity_type="profile_target",
            entity_id=f"{profile.id}:{field}",
            old_values={"value": str(ov) if ov is not None else None},
            new_values={
                "value": str(nv) if nv is not None else None,
                "source": source,
                "by_user_id": by_user.id if by_user else None,
                "reason": reason or "",
            },
        )
    except Exception:
        # AuditLog — best-effort. Основная история уже в ProfileTargetAudit.
        pass


def get_field_source(profile, field: str) -> str:
    """Текущий источник правки поля = source последней записи ProfileTargetAudit.

    Если записей нет — возвращает 'auto' (значит можно перетирать).
    """
    from .models import ProfileTargetAudit

    last = (
        ProfileTargetAudit.objects.filter(profile=profile, field=field)
        .order_by("-at")
        .first()
    )
    return last.source if last else "auto"


def is_locked(profile, field: str) -> bool:
    """Поле залочено для авторасчёта = последняя правка от user/specialist."""
    return get_field_source(profile, field) in ("user", "specialist")
