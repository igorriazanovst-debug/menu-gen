"""Freemium-квота на генерацию меню.

Бесплатный тариф (`plan.code='free'`) даёт ограниченное число генераций меню в
календарный месяц; premium — без лимита. Лимит берётся из `features` free-плана
(`menu_generations_per_month`), с фолбэком на константу.

Учёт — модель `MenuGenerationCounter` (OneToOne→Family) со сбросом по месяцу.
"""

from datetime import date

from django.utils import timezone

from .models import MenuGenerationCounter, SubscriptionPlan
from .permissions import has_active_premium

FREE_PLAN_CODE = "free"
DEFAULT_FREE_MENU_GENERATIONS = 4
DEFAULT_FREE_MAX_FAMILY_MEMBERS = 1


def _current_period_start() -> date:
    """1-е число текущего месяца (по локальному времени)."""
    today = timezone.localdate()
    return today.replace(day=1)


def _next_period_start() -> date:
    """1-е число следующего месяца."""
    today = timezone.localdate()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def _free_plan():
    return SubscriptionPlan.objects.filter(code=FREE_PLAN_CODE, is_active=True).first()


def free_max_family_members() -> int:
    """Эффективный лимит участников для семьи без подписки (free)."""
    plan = _free_plan()
    if plan:
        return plan.max_family_members
    return DEFAULT_FREE_MAX_FAMILY_MEMBERS


def menu_quota_limit(family):
    """Лимит генераций меню за период. None == безлимит (premium)."""
    if has_active_premium(family):
        return None
    plan = _free_plan()
    if plan:
        try:
            return int(plan.features.get("menu_generations_per_month", DEFAULT_FREE_MENU_GENERATIONS))
        except (TypeError, ValueError, AttributeError):
            return DEFAULT_FREE_MENU_GENERATIONS
    return DEFAULT_FREE_MENU_GENERATIONS


def menu_quota_used(family) -> int:
    """Сколько генераций уже потрачено в текущем периоде (0 при смене месяца)."""
    if family is None:
        return 0
    counter = MenuGenerationCounter.objects.filter(family=family).first()
    if counter is None or counter.period_start != _current_period_start():
        return 0
    return counter.count


def menu_quota_reset_at(family) -> date:
    """Дата ближайшего сброса квоты (1-е число следующего месяца)."""
    return _next_period_start()


def can_generate_menu(family) -> bool:
    """Дешёвая предпроверка (без блокировок) для UX."""
    limit = menu_quota_limit(family)
    if limit is None:
        return True
    return menu_quota_used(family) < limit


def try_consume_menu_generation(family) -> bool:
    """Атомарно списать одну генерацию. Возвращает True, если списание прошло.

    Должна вызываться внутри transaction.atomic(): берёт row-lock на счётчик,
    чтобы исключить гонку при параллельных генерациях у одной семьи. Premium →
    всегда True без записи в счётчик.
    """
    limit = menu_quota_limit(family)
    if limit is None:
        return True

    period = _current_period_start()
    counter, _ = MenuGenerationCounter.objects.select_for_update().get_or_create(
        family=family, defaults={"period_start": period, "count": 0}
    )
    if counter.period_start != period:
        counter.period_start = period
        counter.count = 0

    if counter.count >= limit:
        counter.save(update_fields=["period_start", "count", "updated_at"])
        return False

    counter.count += 1
    counter.save(update_fields=["period_start", "count", "updated_at"])
    return True


def menu_quota_summary(family) -> dict:
    """Сводка для фронта: used / limit (None=безлимит) / reset_at."""
    return {
        "used": menu_quota_used(family),
        "limit": menu_quota_limit(family),
        "reset_at": menu_quota_reset_at(family).isoformat(),
    }
