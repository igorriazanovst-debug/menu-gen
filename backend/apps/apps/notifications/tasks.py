"""
Celery-задачи:
  - check_fridge_expiry      — уведомления об истекающих продуктах (ежедневно)
  - expire_subscriptions     — смена статуса просроченных подписок (ежедневно)
  - send_menu_reminder       — напоминание сгенерировать меню (еженедельно)
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_fridge_expiry(self):
    """Создаёт уведомление, если продукт истекает через <=3 дней."""
    try:
        from apps.fridge.models import FridgeItem
        from apps.notifications.models import Notification
        from apps.family.models import FamilyMember

        cutoff = timezone.now().date() + timedelta(days=3)
        expiring = FridgeItem.objects.filter(
            is_deleted=False,
            expiry_date__lte=cutoff,
            expiry_date__isnull=False,
        ).select_related("family")

        notified = 0
        for item in expiring:
            heads = FamilyMember.objects.filter(family=item.family, role="head").select_related("user")
            for head in heads:
                already = Notification.objects.filter(
                    user=head.user,
                    notification_type=Notification.Type.FRIDGE_EXPIRY,
                    action_url="/fridge/{}/".format(item.id),
                    created_at__date=timezone.now().date(),
                ).exists()
                if not already:
                    Notification.objects.create(
                        user=head.user,
                        notification_type=Notification.Type.FRIDGE_EXPIRY,
                        title="Истекает срок годности",
                        message='Продукт "{}" истекает {}.'.format(item.name, item.expiry_date),
                        action_url="/fridge/{}/".format(item.id),
                    )
                    notified += 1

        log.info("check_fridge_expiry: создано %d уведомлений", notified)
        return notified
    except Exception as exc:
        log.error("check_fridge_expiry error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_subscriptions(self):
    """Переводит просроченные подписки в статус EXPIRED."""
    try:
        from apps.subscriptions.models import Subscription

        now = timezone.now()
        updated = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            expires_at__lt=now,
        ).update(status=Subscription.Status.EXPIRED)

        log.info("expire_subscriptions: истекло %d подписок", updated)
        return updated
    except Exception as exc:
        log.error("expire_subscriptions error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_menu_reminder(self):
    """Напоминает пользователям без активного меню на текущую неделю."""
    try:
        from apps.family.models import Family
        from apps.menu.models import Menu
        from apps.notifications.models import Notification

        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())

        families_with_menu = set(
            Menu.objects.filter(
                status=Menu.Status.ACTIVE,
                start_date__gte=week_start,
            ).values_list("family_id", flat=True)
        )

        notified = 0
        for family in Family.objects.exclude(id__in=families_with_menu).select_related("owner"):
            Notification.objects.create(
                user=family.owner,
                notification_type=Notification.Type.MENU_READY,
                title="Пора составить меню",
                message="Вы ещё не создали меню на эту неделю. Сгенерируйте его прямо сейчас!",
                action_url="/menu/generate/",
            )
            notified += 1

        log.info("send_menu_reminder: отправлено %d напоминаний", notified)
        return notified
    except Exception as exc:
        log.error("send_menu_reminder error: %s", exc)
        raise self.retry(exc=exc)
